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
