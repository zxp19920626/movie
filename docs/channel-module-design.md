# App 分发平台模块（channel_pack）设计文档

> 这是一个**多租户内部 SaaS 模块**，不是 movie 内部模块。
> 它管理多个 App（movie 是第一个租户）的 Android 多渠道包 + 自升级（强制/灰度/分组）。
> v1 在 movie monorepo 同 docker-compose 内；触发条件达成后可抽离为独立服务。

---

## 1. 模块定位

| 项 | 内容 |
|---|---|
| 域 | Mobile App Distribution Management |
| 形态 | 多租户内部 SaaS |
| 路径 | `backend/app/modules/channel_pack/` |
| API 命名空间 | `/api/v1/cp/...`（公开）+ `/api/v1/admin/cp/...`（后台） |
| 业务对象 | App（租户）、渠道、版本、升级规则、签名 Job |
| 不依赖 | user / content / admin 模块的任何 internal model |
| 依赖（接口） | IAuthGuard / ITaskQueue / IObjectStore / ICdnRefresher / IClock |
| 抽离触发 | DAU > 10w 且接入第 2 个 App，或 cp 写 QPS > 主业务 30% |

---

## 2. 数据模型（5 张表）

### 关系图
```
cp_apps (1) ─── (N) cp_channels
            └── (N) cp_app_versions ─── (N) cp_apk_signing_jobs
            └── (N) cp_upgrade_rules
```

### 表字段

#### cp_apps（多租户根）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | snowflake |
| tenant_uuid | varchar(36) unique | 公开 ID（App SDK 内置） |
| name | varchar(64) | "movie", "tools-app-1" |
| owner_admin_user_id | bigint FK | a_admin_users.id |
| api_key_hash | varchar(128) | bcrypt(api_key)，服务端调用用 |
| hmac_secret | varchar(128) | App SDK 端签名用，base64 |
| status | enum | active/suspended/deleted |
| created_at | timestamptz | tz-aware |
| updated_at | timestamptz | |

#### cp_channels
| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | |
| app_id | bigint FK | cp_apps.id |
| code | varchar(32) | 同 app 内唯一，如 "gp" / "apkpure" / "direct" |
| name | varchar(64) | 显示名 |
| is_play_store | bool | true → 后端硬拒升级 |
| signing_strategy | enum | walle/none/play_signed |
| enabled | bool | |
| priority | int | 控制签名任务并发顺序 |
| oss_prefix | varchar(128) | 默认 "apks/{tenant_uuid}/" |
| created_at / updated_at | timestamptz | |

#### cp_app_versions
| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | |
| app_id | bigint FK | |
| version_code | int | 同 app 内唯一，App 实际版本号 |
| version_name | varchar(32) | "1.2.3" |
| master_apk_oss_key | varchar(256) | OSS 路径 |
| master_apk_sha256 | varchar(64) | 校验用 |
| min_supported_version_code | int | 低于此值强升 |
| changelog_i18n | json | `{"en": "...", "id": "...", "vi": "..."}` |
| status | enum | draft/signing/ready/archived |
| uploaded_by | bigint FK | a_admin_users.id |
| uploaded_at | timestamptz | |
| released_at | timestamptz nullable | |

#### cp_upgrade_rules（核心表）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | |
| app_id | bigint FK | |
| name | varchar(128) | 运营起的名 |
| enabled | bool | |
| **目标维度（命中条件）** | | |
| version_code_min | int | 闭区间下界 |
| version_code_max | int | 闭区间上界 |
| channel_codes | json array | 空 = 所有渠道；不允许包含 is_play_store=true 的 code |
| country_codes | json array | ISO-3166-1 alpha-2，空 = 所有 |
| device_id_hash_mod_min | int 0-99 | 灰度区间下界 |
| device_id_hash_mod_max | int 0-99 | 灰度区间上界 |
| **策略维度（命中后）** | | |
| target_version_code | int FK | cp_app_versions.version_code |
| is_force | bool | 强升 |
| can_skip | bool | 弱提示能否跳过 |
| popup_interval_hours | int | 弱提示再提醒间隔 |
| priority | int | 高优先匹配 |
| effective_from | timestamptz | |
| effective_to | timestamptz | |
| created_at / created_by | timestamptz / bigint FK | |

#### cp_apk_signing_jobs（幂等性核心）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | |
| app_id | bigint FK | |
| version_code | int | |
| channel_code | varchar(32) | |
| master_sha256 | varchar(64) | 母包指纹 |
| **idempotency_key** | varchar(128) **unique** | hash(app_id + version_code + channel_code + master_sha256) |
| status | enum | pending/running/success/failed |
| output_oss_key | varchar(256) | |
| output_sha256 | varchar(64) | |
| output_size | bigint | |
| attempts | int | |
| last_error | text | |
| worker_id | varchar(64) | 谁在跑 |
| started_at | timestamptz nullable | |
| finished_at | timestamptz nullable | |
| cdn_warmup_status | enum | pending/done/failed |

---

## 3. API 详细规范

### 3.1 公开 API（App 端）

#### GET /api/v1/cp/upgrade/check

**Query 参数**：
- `app_id` (required) — cp_apps.tenant_uuid
- `version_code` (required, int)
- `channel` (required, str)
- `device_id` (required, str)
- `country` (optional, str, ISO-3166-1)

**Headers**：
- `X-CP-Timestamp`：Unix 秒级时间戳，5min 内有效
- `X-CP-Signature`：`HMAC-SHA256(hmac_secret, f"{app_id}\n{version_code}\n{channel}\n{device_id}\n{country}\n{timestamp}")` Base64

**Response 200**（有更新）：
```json
{
  "has_update": true,
  "target_version_code": 102,
  "target_version_name": "1.0.2",
  "is_force": false,
  "can_skip": true,
  "popup_interval_hours": 24,
  "download_url": "https://apk.cdn/.../signed-url-token=...",
  "sha256": "abc123...",
  "size": 52428800,
  "changelog": "Bug fixes and improvements"
}
```

**Response 200**（无更新 / Play 渠道）：
```json
{ "has_update": false }
```

**Response 401**：HMAC 校验失败 / 时间戳过期 / app_id 不存在

**Response 429**：限流

#### GET /api/v1/cp/apk/{channel_code}/{version_code}?app_id=xxx
302 redirect 到 CDN 签名 URL，签名带 5min 过期。同样需要 HMAC 头。

#### GET /api/v1/cp/healthz
独立健康检查，给 UptimeRobot 拨测。返回 `{"status": "ok"}`。

### 3.2 后台 API（管理员）

所有路径前缀 `/api/v1/admin/cp/`，需要 admin JWT + scope=admin + a_admin_users.app_scope 包含目标 app_id。

| Path | Method | 说明 |
|---|---|---|
| `/apps` | GET POST | 列表 / 创建（仅超管） |
| `/apps/{id}` | GET PATCH DELETE | |
| `/apps/{id}/regenerate-keys` | POST | 重生 API key + HMAC secret（旧的进黑名单） |
| `/apps/{app_id}/channels` | GET POST | |
| `/apps/{app_id}/channels/{id}` | PATCH DELETE | |
| `/apps/{app_id}/versions` | GET POST | |
| `/apps/{app_id}/versions/{id}` | GET DELETE | |
| `/apps/{app_id}/versions/{id}/upload-token` | POST | OSS STS 直传凭证 |
| `/apps/{app_id}/versions/{id}/finalize` | POST | 触发 fan-out 签名 |
| `/apps/{app_id}/rules` | GET POST | |
| `/apps/{app_id}/rules/{id}` | PATCH DELETE | |
| `/apps/{app_id}/rules/preview` | POST | 输入 sample 设备预览命中规则 |
| `/apps/{app_id}/signing-jobs` | GET | 列表 + 状态 |
| `/apps/{app_id}/signing-jobs/{id}/retry` | POST | 手动重试 |

---

## 4. HMAC 签名详细规范

### 签名算法
```
canonical_string = f"{app_id}\n{version_code}\n{channel}\n{device_id}\n{country}\n{timestamp}"
signature = base64(hmac_sha256(hmac_secret_bytes, canonical_string.encode()))
```

### 服务端校验流程
1. 取 `X-CP-Timestamp`，校验 `abs(now - ts) < 300`（5min）
2. 取 `app_id`，从 cp_apps 加载（Redis 缓存 60s）
3. 用 cp_apps.hmac_secret 重算 signature
4. 与 `X-CP-Signature` 常数时间比较（hmac.compare_digest）
5. 任何不匹配 → 401 + Sentry 告警

### Replay 防御
- 5min 时间窗 + 时间戳校验
- 不需要 nonce（窗口够短，配合 Cloudflare 限流）

### 密钥泄露应对
- 调 `/apps/{id}/regenerate-keys` 重生 hmac_secret
- 旧 secret 进 Redis 黑名单 24h（让在途请求平滑过渡）
- App SDK 配置远程下发 secret（v2，避免下次发版才能换）

---

## 5. Walle 渠道签名工作流

### 触发流程
```
admin POST /apps/{app_id}/versions/{id}/finalize
  ↓
signing_service.fan_out_signing_jobs(version_id):
  for channel in channels WHERE app_id=? AND enabled=true AND is_play_store=false:
    create cp_apk_signing_jobs 行（idempotency_key 唯一）
    enqueue celery task sign_apk(job_id)
  ↓
celery worker:
  SELECT FOR UPDATE SKIP LOCKED job
  if status == success: return  # 幂等
  if status == running and started_at < now - 10min: 接管
  ↓
  下载母包到 /tmp → 校验 SHA256 → walle 注入 → 算 SHA256 → 上传 OSS → CDN 预热 → 写回
  ↓
  signing_service 检查"该版本所有 jobs success" → 置 cp_app_versions.status=ready
```

### 失败重试策略
```python
@celery.task(
    autoretry_for=(IOError, subprocess.CalledProcessError, OSSError),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
    retry_jitter=True,
)
def sign_apk(job_id): ...
```
全失败 → status=failed + 写 last_error → admin 在 signing-jobs 页看到红条手动 retry。

### CDN 预热失败处理
不阻断主流程；写 `cdn_warmup_status=failed` 让运维看到。下次升级请求自然回源 + 边缘缓存。

### 为什么必须预生成
1. 1M DAU 实时签名 → Java 子进程每次 1-3s → 单 ECS 1000 QPS 直接打死
2. 实时签 URL/内容每次不同 → CDN 命中率 0 → 100% 回源 → 每天 500GB 出口带宽
3. Play 审核员反编译看到"动态分发的 APK"判违规风险更高

---

## 6. 升级规则引擎核心算法

### 决策伪代码
```python
def check_upgrade(app_id, version_code, channel, country, device_id):
    # 1. Play 渠道硬拒（双保险，编译期已隔离）
    ch = get_channel(app_id, channel)
    if ch is None or ch.is_play_store:
        return NO_UPDATE

    # 2. 缓存命中
    hash_bucket = crc32(device_id) % 100
    cache_key = f"cp:upgrade:{app_id}:{version_code}:{channel}:{country}:{hash_bucket}"
    if cached := cache.get(cache_key):
        return cached

    # 3. 候选规则查询（DB 索引：app_id + enabled + priority desc）
    now = clock.now()
    candidates = db.query(cp_upgrade_rules).filter(
        app_id == app_id,
        enabled == True,
        effective_from <= now <= effective_to,
        version_code_min <= version_code <= version_code_max,
        channel_codes.is_empty() | channel_codes.contains(channel),
        country_codes.is_empty() | country_codes.contains(country),
        device_id_hash_mod_min <= hash_bucket <= device_id_hash_mod_max,
    ).order_by(priority.desc(), created_at.desc())

    # 4. 遍历候选，找第一个目标已就绪的
    for rule in candidates:
        target = get_app_version(rule.target_version_code)
        if not target or target.status != 'ready':
            continue
        if target.version_code <= version_code:
            continue  # 不降级
        signed = get_signing_job(target.version_code, channel)
        if not signed or signed.status != 'success':
            continue  # 这渠道还没签好

        result = UPDATE_HIT(target, signed.output_oss_key, rule)
        cache.set(cache_key, result, ttl=300)
        return result

    cache.set(cache_key, NO_UPDATE, ttl=300)
    return NO_UPDATE
```

### Cache 失效
任何 cp_upgrade_rules / cp_app_versions / cp_apk_signing_jobs 写入 → invalidate `cp:upgrade:{app_id}:*`。

### 强升 vs 灰度的表达
同一个 target_version_code 上挂多条 rule：
- 强升规则：`is_force=true, priority=100`，不限国家、不限灰度
- 灰度规则：`is_force=false, priority=50, device_id_hash_mod_max=20`（20% 灰度）

引擎按 priority 顺序判，强升优先。

### 性能目标
- p50 < 50ms（Redis 命中）
- p95 < 200ms（DB 查询）
- p99 < 500ms（兜底告警阈值）

---

## 6.1 升级弹窗按钮（popup_buttons）

> 给运营更灵活的弹窗按钮控制：可下发多语言文案、多类型跳转（外链 / 应用市场 / In-App 下载 APK / Deeplink），同时兜底 Play 合规与 URL 白名单。
> 设计目标：**Play 渠道永不下发可绕过 Play 的安装路径**、**老客户端零回归**、**所有按钮 url 必须 https 且 host 在白名单**。

### 6.1.1 数据模型

`cp_upgrade_rules.popup_buttons` 新增 JSON 字段（nullable，默认 `null`）。

**最大长度**：5（数组元素数 max=5，超过 422）。

**单元素 schema**（Pydantic 严格，extra="forbid"）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | str | 是 | 同一规则内唯一；客户端用作埋点 key |
| `type` | enum | 是 | `browser` / `playstore` / `inapp_apk` / `deeplink` / `none` |
| `text_i18n` | dict[str, str] | 是 | locale → 文案；至少有 `en` |
| `url_i18n` | dict[str, str] | type≠none | locale → URL；至少有 `en`（`type=none` 时必须省略或 `{}`） |
| `style` | enum | 否 | `primary` / `secondary` / `text`；默认 `secondary` |
| `target` | str | 否 | 客户端跳转参数（如 deeplink 路径），按 type 语义解释 |

### 6.1.2 type 枚举（5 个，固定，禁止扩展）

| type | 客户端行为 | 备注 |
|---|---|---|
| `browser` | 浏览器外打开 url | 适合落地页 / FAQ |
| `playstore` | 拉起 Play Store 应用页 | url 必须是 `https://play.google.com/store/apps/details?id=...` 形式 |
| `inapp_apk` | 在 App 内下载 APK 并触发安装 | **Play 渠道禁用**（红线 #2） |
| `deeplink` | 解析 `target` 内部跳转 | url 仅作降级回退用，仍受白名单约束 |
| `none` | 仅关闭弹窗、不跳转 | 用作"我知道了" / "稍后提醒"等纯关闭按钮；不带 url |

⚠️ **不存在** `dismiss` / `cancel` / `confirm` 等老命名；本字段语义是「跳转动作」，关闭交互归 `none`。

### 6.1.3 Play 渠道硬约束（防 Google 下架，三道闸）

**第一道——保存规则时**：`RuleCreate` / `RuleUpdate` Service 入口校验：

```python
if rule.popup_buttons:
    for btn in rule.popup_buttons:
        if btn.type == "inapp_apk":
            # 该 rule 的 channel_codes 含任一 is_play_store=true 渠道
            # 或 channel_codes 为空（apply-to-all 也走 Play 兜底）
            if rule_targets_play_channel(app_id, rule.channel_codes):
                raise HTTPException(422, "inapp_apk not allowed on Play channel")
```

`channel_codes=[]`（apply-to-all）等价于"包含所有渠道（含 Play）"，因此**也必须**走兜底校验。

**第二道——切渠道 `is_play_store=false→true` 时**：`rescan_existing_rules(channel_id)`：

```python
def toggle_play_store(channel_id, new_value):
    if new_value is True:
        violations = scan_rules_with_inapp_apk_targeting(channel_id)
        if violations:
            raise HTTPException(409, {
                "error": "existing_rules_have_inapp_apk",
                "violations": [{"rule_id": r.id, "name": r.name} for r in violations]
            })
    channel.is_play_store = new_value
```

**第三道——查询 /upgrade/check 时**：is_play_store=true 渠道直接返回 `{"has_update": false}`，不查规则、不渲染按钮（与 §7 第三道闸一致）。

### 6.1.4 URL 白名单（cp_apps.allowed_upgrade_hosts）

**字段**：`cp_apps.allowed_upgrade_hosts` JSON array of string。

**Host 形态约束**（schema 强制）：
- 纯 host：`apk.movie.app`、`play.google.com`
- ❌ 不含 scheme（`https://...`）
- ❌ 不含 path / query（`apk.movie.app/files`）
- ❌ 不含 port（`apk.movie.app:443`）
- ✅ 全小写（保存时小写化，比对时也小写）
- ✅ 允许子域单独白名单（`cdn.movie.app` ≠ `movie.app`，**不做后缀匹配**）

**校验时机**：
- 保存规则（RuleCreate/Update）：对每个 button 的 `url_i18n` 各 locale，提取 host → 若不在 `allowed_upgrade_hosts` → 422
- 缩短白名单（PATCH `/apps/{id}` 删 host）：若该 host 被任一现存规则的某 button.url 引用 → 409 + `affected_rules` 列表，阻塞保存

```python
def validate_button_url(url: str, allowed_hosts: list[str]):
    if not url.startswith("https://"):
        raise HTTPException(422, "url must be https")
    host = urlparse(url).hostname.lower()
    if host not in [h.lower() for h in allowed_hosts]:
        raise HTTPException(422, f"host {host} not in allowed_upgrade_hosts")
```

### 6.1.5 https-only

所有 `url_i18n` 的值必须以 `https://` 开头；`http://` / `ftp://` / `file://` / `javascript:` 一律 422。

### 6.1.6 i18n fallback 算法

服务端 `/upgrade/check` 在 resolve 时按以下顺序选 locale：

```python
def choose_locale(country: str | None, accept_language: str | None) -> list[str]:
    """返回 locale 候选链，从最具体到最 fallback。"""
    chain = []
    # 1. Accept-Language 前几位（按 q 排序），如 vi-VN, en-US
    if accept_language:
        chain.extend(parse_accept_language(accept_language))  # ["vi-VN", "vi", "en-US", "en"]
    # 2. country → 默认 locale（VN→vi, ID→id, TH→th, PH→en, ...）
    if country:
        chain.append(COUNTRY_DEFAULT_LOCALE.get(country.upper(), "en"))
    # 3. 兜底 en
    chain.append("en")
    # 去重保序
    return list(dict.fromkeys(chain))


def pick_i18n(i18n_dict: dict[str, str] | None, locale_chain: list[str]) -> str | None:
    if not i18n_dict:
        return None
    for loc in locale_chain:
        if loc in i18n_dict:
            return i18n_dict[loc]
        # 退化：vi-VN → vi
        base = loc.split("-")[0]
        if base in i18n_dict:
            return i18n_dict[base]
    # 任意取一个（i18n_dict 至少有 en，前面会命中；这里是 paranoia）
    return next(iter(i18n_dict.values()), None)
```

### 6.1.7 缺 url 整按钮丢弃（resolve_popup_buttons）

服务端 `resolve_popup_buttons(buttons, locale_chain)`：

```python
def resolve_popup_buttons(buttons, locale_chain):
    resolved = []
    for btn in buttons or []:
        text = pick_i18n(btn.text_i18n, locale_chain)
        if not text:
            continue  # 文案 fallback 也拿不到 → 丢弃整按钮
        url = None
        if btn.type != "none":
            url = pick_i18n(btn.url_i18n, locale_chain)
            if not url:
                continue  # url fallback 拿不到 → 丢弃整按钮（避免下发空 url）
        resolved.append({
            "id": btn.id,
            "type": btn.type,
            "text": text,
            "url": url,        # type=none 时为 None；其他 type 必定非空
            "style": btn.style or "secondary",
            "target": btn.target,
        })
    return resolved
```

⇒ **客户端拿到的 button.url 永远不会为 null，除非 type='none'**。

### 6.1.8 兼容性矩阵（C5 关键，老客户端零回归）

`/upgrade/check` response 在有更新时**同时下发**老 4 字段（`popup_title` / `popup_content` / `popup_confirm` / `popup_cancel`）+ 新 `popup_buttons`，由客户端按自己版本能力选用：

| 服务端 `popup_buttons` 值 | 老客户端（不识别 popup_buttons） | 新客户端 |
|---|---|---|
| 字段不存在（response 中无 key） | 走老 4 字段 | 走老 4 字段（看作降级） |
| `[]` 空数组 | 走老 4 字段 | 走老 4 字段 |
| 非空数组 | **走老 4 字段**（字段不识别即忽略） | **优先用 popup_buttons**；老 4 字段冗余下发用于兜底 |

实现约定：
- 即便规则配了 `popup_buttons`，服务端**仍然**输出 `popup_title` / `popup_content` / `popup_confirm` / `popup_cancel`（取规则的传统字段或从 buttons 推导一个 best-effort 默认值）。
- 老客户端读不到 `popup_buttons` key 时不会崩溃（JSON 多余字段忽略）。
- 缓存 key 保持原 schema 不变；popup_buttons 是 response 的纯增量，缓存命中时直接复用整个 JSON。

### 6.1.9 Response 示例

```json
{
  "has_update": true,
  "target_version_code": 102,
  "target_version_name": "1.0.2",
  "is_force": false,
  "can_skip": true,
  "popup_interval_hours": 24,
  "popup_title": "新版本可用",
  "popup_content": "修复若干问题",
  "popup_confirm": "立即更新",
  "popup_cancel": "稍后",
  "popup_buttons": [
    {
      "id": "primary_update",
      "type": "inapp_apk",
      "text": "立即更新",
      "url": "https://apk.movie.app/v102/direct.apk",
      "style": "primary"
    },
    {
      "id": "later",
      "type": "none",
      "text": "稍后再说",
      "url": null,
      "style": "text"
    }
  ],
  "download_url": "https://apk.cdn/.../signed-url-token=...",
  "sha256": "abc123...",
  "size": 52428800,
  "changelog": "Bug fixes and improvements"
}
```

---

## 7. Play 渠道隔离（三道闸）

### 第一道：编译期 BuildConfig flavor（根本防线）
```gradle
// app/build.gradle
android {
  productFlavors {
    selfhosted {
      dimension "channel"
      buildConfigField "boolean", "SELF_UPGRADE_ENABLED", "true"
      buildConfigField "String", "CHANNEL", '"direct"'
    }
    gp {
      dimension "channel"
      buildConfigField "boolean", "SELF_UPGRADE_ENABLED", "false"
      buildConfigField "String", "CHANNEL", '"gp"'
    }
  }
  sourceSets {
    selfhosted { java.srcDirs = ['src/selfhosted/java'] }
    gp { java.srcDirs = ['src/gp/java'] }
  }
}
```
gp flavor 用 `src/gp/java/.../upgrade/PlayUpgradeStub.kt` 替代 SelfUpgradeManager，整个升级类**编译期不打进 gp 包**，反编译都找不到。

### 第二道：运行时（双保险）
```kotlin
if (BuildConfig.SELF_UPGRADE_ENABLED && BuildConfig.CHANNEL != "gp") {
    SelfUpgradeManager.checkUpgrade(...)
}
```

### 第三道：后端硬拒
```python
@router.get("/upgrade/check")
async def check_upgrade(channel: str, ...):
    ch = await get_channel(app_id, channel)
    if ch is None or ch.is_play_store:
        return {"has_update": false}
    # ... 不查规则
```

### CI 闸
GitHub Actions：
```yaml
- name: Verify Play build excludes self-upgrade
  if: matrix.flavor == 'gp'
  run: |
    unzip app-gp-release.apk -d /tmp/apk
    if grep -r "SelfUpgradeManager" /tmp/apk/; then
      echo "FAIL: SelfUpgradeManager found in Play build"
      exit 1
    fi
```

---

## 8. 多租户接入流程

### 注册一个新 App（管理员超管操作）
1. POST `/api/v1/admin/cp/apps` 创建 cp_apps 记录
2. 系统生成 `tenant_uuid` + `api_key`（明文一次性返回，hash 存 DB）+ `hmac_secret`
3. 给 owner_admin_user_id 赋 app_scope 权限
4. App 端 SDK 集成：在 BuildConfig 写入 `app_id=tenant_uuid` + `hmac_secret`（编译期注入）
5. 服务端调用方：把 api_key 存进自己的 secret manager
6. 在新 App 的 admin 后台测试 /upgrade/check，跑通 → 上线

### App SDK 端配置示例（Android）
```kotlin
// app/build.gradle
buildConfigField "String", "CP_APP_ID", "\"${cpAppId}\""  // 从 gradle.properties 读
buildConfigField "String", "CP_HMAC_SECRET", "\"${cpHmacSecret}\""
buildConfigField "String", "CP_BASE_URL", "\"https://api.movie.app/api/v1/cp\""
```
gradle.properties（**进 .gitignore，CI 从 secret 注入**）：
```
cpAppId=11111111-2222-3333-4444-555555555555
cpHmacSecret=base64-32-bytes-secret
```

### movie-main 后端调 cp（服务端调用）
```python
# 不通过 HMAC，通过 API key
client = ChannelPackClient(
    base_url=settings.CP_BASE_URL,
    api_key=settings.CP_API_KEY,  # 仅服务端持有
)
result = await client.list_channels(app_id=settings.CP_MOVIE_APP_ID)
```
未来 cp 抽离独立 ECS：只改 settings.CP_BASE_URL 即可。

---

## 9. 抽离独立服务的迁移路径

### 现在做（v1）
- 模块边界清晰、依赖只走接口、`public.py` 是唯一对外契约
- DB 表名都加前缀 `cp_`（未来抽离时整体迁走）
- 跨模块调用走 `ChannelPackPublicService` 类的方法
- 配置项前缀 `CHANNEL_PACK_*`（OSS bucket、CDN 域名、Walle JAR 路径都独立）
- Alembic multi-head：channel_pack 模块的迁移单独一棵树

### 抽离时（v2，触发条件达成后）
- 接口稳定 → `ChannelPackPublicService` 包成 HTTP client，业务代码改 import client，不改逻辑
- 独立 DB schema → `cp_*` 表整体 dump 迁到独立 RDS 实例
- 独立部署 → 单独 docker image + 单独 ECS 或 K8s pod，nginx 路径转发 `/api/v1/cp/*` 过去
- 独立监控 → cp 自己的 Sentry project + 自己的 Telegram 告警 channel

### 抽离触发条件（写死，不"视情况而定"）
- DAU > 10w 且**接入第 2 个 App**（满足复用前提），或
- 渠道包模块 DB 表写 QPS 占总 DB 写 30% 以上，或
- 升级 check 接口 p99 抖动影响其它接口（共享 worker pool 干扰），或
- 渠道包逻辑要独立 release cadence（一周改两次签名规则，不想动主仓库）

任一条达成 → 开抽离工单。否则不动。

---

## 10. 模块依赖契约（import-linter 强制）

### 允许 import
- `app.core.*`：config, security_protocol, ids, clock, errors
- `app.shared.*`：repository_base, cache_service, media_provider（不会用但允许）
- `app.adapters.*`：sentry, structlog, redis_pool, celery_app
- 标准库 + 第三方包

### 禁止 import
- `app.modules.user.*` ← CI 拒
- `app.modules.content.*` ← CI 拒
- `app.modules.admin.*` ← CI 拒（admin_users 通过 IAuthGuard 接口访问）

### .importlinter 配置示例
```ini
[importlinter]
root_packages = app

[importlinter:contract:channel_pack-isolation]
name = channel_pack must not import sibling modules
type = forbidden
source_modules = app.modules.channel_pack
forbidden_modules = app.modules.user, app.modules.content, app.modules.admin
```

---

## 11. 已知技术债与未来扩展

### v1 接受的债
- HMAC secret 在 App SDK 编译期注入，泄露后只能发版换；v2 上远程下发
- cp 与 main 同进程，共享 fastapi worker pool；高负载时互相干扰
- 同 RDS 实例，cp 的 DDL 锁可能影响主业务；DAU 起来前不解决
- Alembic multi-head 在多人协作时偶尔需要手动 merge head；单人开发不痛

### v2 候选扩展
- 增量升级（bsdiff）：百万级带宽紧张时上
- 预下载 + 静默安装（Android 12+）
- 灰度策略支持白名单（device_id 列表）
- A/B 测试 hook（不同灰度组下发不同 apk 测留存）
- WebHook：升级事件回调给租户业务系统
- 跨地域分发：基于 country 路由不同 CDN

### 永远不做
- 自建签名服务（Walle 够用，自研零收益）
- 自建 OSS（直接用阿里云，迁移走 abstraction）
- 实时签名（已说明）

---

## 12. 测试策略

### 单元测试（pytest）
- 升级规则引擎：所有边界（版本范围 / 灰度 / 强升覆盖 / Play 排除 / 过期 / 优先级）
- HMAC 校验：正确签名 / 时间过期 / 签名错误 / app_id 不存在
- 幂等性：同 idempotency_key 不重签
- 多租户隔离：租户 A 的请求看不到租户 B 的数据

### 集成测试
- staging 环境跑：注册租户 → 上传 APK → 签名 → check 接口验证 → 下载 → SHA256 校验
- 跨租户隔离测试

### 压测
- Locust 1000 并发打 /upgrade/check，目标 p95 < 200ms
- 上线前必须跑过

---

## 附：术语表

- **租户（Tenant）**：cp_apps 一行 = 一个 App 客户。movie 是第一个租户。
- **app_id**：tenant_uuid 的别名，对外暴露的 ID。
- **api_key**：服务端调用 cp 的凭证，走 Header `X-CP-Api-Key`。
- **hmac_secret**：App 端 SDK 调 cp 的签名密钥，仅 App SDK + cp 后端持有。
- **idempotency_key**：cp_apk_signing_jobs 唯一键，决定签名任务幂等。
- **device_id_hash_mod**：crc32(device_id) % 100，用于灰度命中。
- **Play 渠道**：is_play_store=true 的渠道，永远不下发自升级。
