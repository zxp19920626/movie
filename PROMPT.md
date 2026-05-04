# movie 项目 — Claude Code 主提示词（v2 红蓝二轮后定稿）

> 用法：开新会话时把这份文件整体粘贴给 Claude Code，或者第一句话说
> "请先读 /Users/yikong/Downloads/work/movie/PROMPT.md 再开始工作"。
> 这份文件是项目的"长期宪法"——写代码、改架构、部署前都要对照。

---

## 1. 项目身份

- **项目目录**：`/Users/yikong/Downloads/work/movie`（monorepo）
- **类型**：海外影视 App 服务端 + Vue 管理后台 + **独立 App 分发平台模块（多租户）**
- **目标用户**：东南亚（印尼/越南/菲律宾/泰国）+ 中东 + 拉美 + 非洲；不服务国内、不备案
- **12 个月目标 DAU**：100w；起步预算每月几百美元
- **开发者**：单人 Android 出身，零后端 / 零运维经验，后期会交接

### ⭐ 战略核心
**App 分发平台 = 内部多租户 SaaS**，不是 movie 的内部模块：
- 模块代码独立（`backend/app/modules/channel_pack/`）
- **数据多租户隔离**（所有 `cp_*` 表带 `app_id` FK）
- 对外 API 中性命名（`/api/v1/cp/...`，不绑 movie）
- movie 是它的第一个租户；未来可服务其它影视/工具类 App
- 物理上 v1 与 movie 同 docker-compose；触发条件达成后可抽离独立部署

---

## 2. 锁定技术栈（红蓝二轮后已定稿，不再讨论）

| 层 | 选择 |
|---|---|
| 后端 | FastAPI + SQLAlchemy + **alembic 多 head（按模块分迁移历史）** |
| 数据库 | **阿里云国际 RDS for MySQL 8.0**（不自建） |
| 缓存/队列 | Redis（缓存 + Celery broker + 限流 + JWT 黑名单） |
| 异步任务 | Celery + celery-beat |
| 前端 | Vue3 + Vite + TS + Element Plus + Pinia |
| 云 | 阿里云国际版（**非国内版**） |
| 静态/APK | OSS + 阿里云 CDN |
| 视频 | 阿里云 VOD（**仅技术运维登控制台**；业务代码走 `media_provider` 抽象层） |
| 防护 | Cloudflare 免费版（WAF + Turnstile + **海外流量套源**省 VOD 流量费） |
| 认证 | Email + Google + 手机 OTP；高费率国家用 WhatsApp OTP |
| Web | Nginx |
| 容器化 | Docker + docker-compose 起步，K8s-ready 抽象（不预先实现 region 分支） |
| CI/CD | GitHub Actions |
| 错误监控 | Sentry 免费版 |
| 拨测 | UptimeRobot 免费版 |
| 告警通道 | **Telegram bot**（单人不要 PagerDuty） |
| 资源监控 | 阿里云 CloudMonitor + 预算告警 30/60/90% |
| 模块边界 | **import-linter（CI 强制）** |
| 域名 | 国际注册商（Namecheap / Cloudflare Registrar） |
| HTTPS | Let's Encrypt + 续签健康检查 |

---

## 3. 服务拓扑（v1：单 ECS + docker-compose）

```
公网 → Cloudflare（WAF + Turnstile + 海外流量套源） → 阿里云 ECS:443
                                                        └── nginx
                                                             ├── /api/v1/cp/*    → fastapi-cp（App 分发平台）
                                                             ├── /api/v1/*       → fastapi-main（user/content/admin）
                                                             └── /admin          → admin-web/dist 静态托管

ECS docker-compose 服务：
- nginx
- fastapi-main（无状态多 worker；user + content + admin 模块）
- fastapi-cp（无状态多 worker；channel_pack 模块；可单独扩容）
  ※ v1 也可以合一个进程跑，路径分离便于未来抽离
- celery-worker（多 worker；APK 签名 + VOD sync + OTP）
- celery-beat（单实例定时；K8s 时变 CronJob）
- redis
- filebeat（stdout → 本地 7d + OSS 30d 归档）

外部托管（不在 ECS 上）：
- MySQL → 阿里云 RDS（自动备份 + 跨区快照）
- 静态/APK → OSS + 阿里云 CDN
- 视频 → 阿里云 VOD（技术运维入口）
```

**反模式（绝对禁止）**：
- 写本地盘；in-process 定时任务；in-memory 状态/sticky session
- sqlite/本地文件锁；硬编码 region 分支；config 散落 `os.getenv`
- nginx 直接挂本地目录返用户内容
- **跨模块直接 import 兄弟模块的 model/service**（必须走 public service 接口）

---

## 4. 4 模块结构（B3'）

```
backend/app/
├── core/                  config, security_protocol, deps, exceptions, clock, ids, errors
├── shared/                跨模块共用：base ORM, repository_base, cache_service, media_provider
├── modules/
│   ├── channel_pack/      App 分发平台（多租户）
│   │   ├── __init__.py    只暴露 routers + public service
│   │   ├── public.py      对外契约：ChannelPackPublicService
│   │   ├── routers/       app_routes.py + admin_routes.py
│   │   ├── models/        cp_apps, cp_channels, cp_app_versions, cp_upgrade_rules, cp_apk_signing_jobs
│   │   ├── schemas/
│   │   ├── services/      upgrade_engine, signing_service, channel_service, app_registry
│   │   ├── tasks/         sign_apk, cdn_warmup
│   │   ├── adapters/      object_store, cdn, walle
│   │   └── tests/
│   ├── user/              auth, users, devices, oauth, otp, refresh_tokens
│   ├── content/           categories, videos, episodes, watch_history, region_visibility, vod_sync
│   └── admin/             admin_users, admin_roles, operation_logs, dashboard
├── adapters/              sentry, structlog, redis_pool, celery_app
├── api/v1/                router 聚合（from each module import its routers）
└── main.py
```

**import-linter 规则（CI 强制，违反就 fail）**：
- `channel_pack` 不许 import `user/content/admin` 任何东西
- 横切关注点（auth 接口、operation_logs 接口）必须在 `app.core` 或 `app.shared` 暴露 protocol
- 任何模块禁止 import 兄弟模块的 internal models

---

## 5. 17 张核心表（按模块前缀）

### channel_pack 模块（5 张，前缀 `cp_`）
- **`cp_apps`** ⭐ 多租户根：id, tenant_uuid（公开 ID）, name, owner_admin_user_id, api_key_hash, status, created_at
- **`cp_channels`**：id, **app_id（FK）**, code（同 app 内唯一）, name, is_play_store, signing_strategy, enabled, priority, oss_prefix
- **`cp_app_versions`**：id, **app_id**, version_code, version_name, master_apk_oss_key, master_apk_sha256, min_supported_version_code, changelog_i18n, status（draft/signing/ready/archived）, uploaded_by, uploaded_at, released_at
- **`cp_upgrade_rules`**：id, **app_id**, name, enabled, version_code_min/max, channel_codes(JSON), country_codes(JSON), device_id_hash_mod_min/max, target_version_code, is_force, can_skip, **popup_strategy（enum: once_per_launch / once_per_session / once_per_day / once_per_week / once_per_release / custom_interval）**, popup_interval_hours（仅当 popup_strategy=custom_interval 生效）, **popup_title_i18n / popup_content_i18n / confirm_text_i18n / cancel_text_i18n**（弹窗多语言文案）, priority, effective_from/to
- **`cp_apk_signing_jobs`**（幂等性核心）：id, **app_id**, version_code, channel_code, master_sha256, status, output_oss_key, output_sha256, attempts, last_error, **idempotency_key（unique）**, cdn_warmup_status, started_at, finished_at

### content 模块（5 张，前缀 `ct_`）
- ct_categories（i18n JSON）
- **ct_videos**（标准字段命名：code（"VID-2026-XXXX" 业务编码 unique）, title_i18n, description_i18n, type（movie/series/variety/anime）, category_id, tags(JSON), score, rating, release_year, release_date, duration_min, director, cast_list(JSON), studio, cover_url, poster_url, trailer_url, **vod_file_id（关联 VOD）**, vod_status / vod_duration / vod_cover_url / vod_synced_at（同步快照），required_tier（free/vip/svip 占位字段，未启用时统一 free）, status（draft/published/offline）, secondary_review_status（draft/pending/approved/rejected）, **featured(bool)**, **trending(bool)**, views, recommend_priority, region_whitelist(JSON, deprecated 用 ct_region_visibility 替代), created_at, updated_at）
- ct_video_episodes（id, video_id, season, episode_no, title, duration_min, vod_file_id, video_url）
- ct_watch_history（user_id, video_id, episode_id, position_sec, duration_sec, updated_at；保留每用户最近 N=200）
- **ct_region_visibility**（视频 × 国家二维矩阵；默认 false，运营逐国手动 enable）

### user 模块（5 张，前缀 `u_`）
- u_users, u_user_oauth, u_devices, u_otp_codes, u_refresh_tokens

### admin 模块（3 张，前缀 `a_`）
- a_admin_users（带 `app_scope` 字段：JSON 数组，每个 admin 看哪些 app）
- **a_admin_roles**（细粒度 RBAC：6 大模块 dashboard/cp/content/user/membership/permissions，每模块拆 view/edit 权限点；4 个 seed 角色：Super_Admin（内建全权）/ Content_Manager / Global_Ops / Service_Auditor（只读））
- a_operation_logs（含 `external_identity_id` 关联 RAM 子账号）

### 新增统计/事件表（前缀 `s_`，可选启用）
- **s_analytics_events**（id, event_type（page_view/play_start/play_complete/search/upgrade_check/ad_impression/ad_click）, user_id?, video_id?, page_code?, app_id?, meta(JSON), created_at；按 (event_type, created_at) 和 (page_code, created_at) 加索引）— P5/P6 阶段启用

---

## 6. 核心 API（按模块命名空间）

### App 分发平台对外（公开但 HMAC 保护）
- `GET /api/v1/cp/upgrade/check?app_id=&version_code=&channel=&device_id=&country=`
  - 头部 `X-CP-Signature: HMAC-SHA256(secret, body+timestamp)` + `X-CP-Timestamp`（5min 内有效防 replay）
  - Cloudflare WAF 限流 5 req/min/device + 后端二次校验
- `GET /api/v1/cp/apk/{channel_code}/{version_code}?app_id=` → 302 跳 CDN 签名 URL
- `GET /api/v1/cp/healthz`

### App 分发平台后台
- `/api/v1/admin/cp/apps` CRUD（超管才能建租户）
- `/api/v1/admin/cp/apps/{app_id}/channels` CRUD
- `/api/v1/admin/cp/apps/{app_id}/versions` CRUD + upload-token + finalize（finalize 触发 fan-out 签名）
- `/api/v1/admin/cp/apps/{app_id}/rules` CRUD + preview（输入 sample 设备，预览命中哪条）
- `/api/v1/admin/cp/apps/{app_id}/signing-jobs`（查状态 + retry）

### user 模块
- /api/v1/auth/email/login, /auth/google, /auth/phone/send-otp, /auth/phone/verify, /auth/refresh
- /api/v1/devices/register

### content 模块
- `GET /api/v1/videos` / `GET /videos/{id}` / `GET /videos/{id}/play-token` / `POST /watch-history`
- **`GET /api/v1/videos/home`**（首页聚合：featured + continueWatching + trending + top10，单接口减少 App 端往返）
- **`GET /api/v1/videos/search?q=`**（按 title / director / cast / tags 多字段检索）
- /api/v1/admin/content/videos （含 sync-from-vod、sync-batch、地区可见性矩阵编辑、二次审核流转）

### 埋点 / 分析
- `POST /api/v1/analytics/track`（公开，optionalAuth；事件类型 page_view / play_start / play_complete / search / upgrade_check / ad_impression / ad_click）
- `GET /api/v1/admin/stats/overview`（仪表盘 KPI：DAU / 新订阅 / 收入 / 广告 PV）
- `GET /api/v1/admin/stats/trends`（30 天趋势 + 留存 + 广告位分布，给 ECharts）

### admin 模块
- /api/v1/admin/auth/login（IP 白名单）
- /api/v1/admin/dashboard, /admin/operation-logs

---

## 7. App 分发平台关键设计

### 7.1 Walle 渠道签名工作流（幂等 + 预生成）
1. admin upload 母包前**强制校验 version_code 严格大于该 app 历史最大值**（防止灰度回滚踩坑）
2. admin finalize 母包 → service 创建一批 cp_apk_signing_jobs（每个 enabled & 非 is_play_store 渠道一条）
3. Celery 任务 `idempotency_key = hash(app_id + version_code + channel + master_sha256)`，同 key 已 success 直接复用
4. SELECT FOR UPDATE SKIP LOCKED 防 worker 重复消费
5. 步骤：OSS 下载母包 → walle CLI 注入 → 算 SHA256 → 上传 OSS → CDN 预热 → 写回
6. 失败 retry 3 次（autoretry_for + backoff + jitter）；全失败 status=failed 让 admin 手动 retry

**为什么必须预生成而不是实时**：1M DAU 实时签名 = ECS CPU 炸 + CDN 命中率 0 + 出口带宽爆。

### 7.2 升级规则引擎（纯函数 + Redis 缓存）
```
function check_upgrade(app_id, version_code, channel, country, device_id):
    if channel.is_play_store: return NO_UPDATE        # 后端硬拒
    hash_bucket = crc32(device_id) % 100
    candidates = SELECT cp_upgrade_rules WHERE app_id = ? AND enabled
                 AND now BETWEEN effective_from AND effective_to
                 AND version_code BETWEEN min AND max
                 AND (channel_codes is empty OR channel IN channel_codes)
                 AND (country_codes is empty OR country IN country_codes)
                 AND device_id_hash_mod_min <= hash_bucket <= device_id_hash_mod_max
                 ORDER BY priority DESC, created_at DESC
    for rule in candidates:
        target = get_app_version(rule.target_version_code)
        if not target or target.status != 'ready': continue
        if target.version_code <= version_code: continue
        signed = get_signing_job(target, channel)
        if not signed or signed.status != 'success': continue
        return UPDATE_HIT(...)
    return NO_UPDATE
```
Redis cache key `cp:upgrade:{app_id}:{version_code}:{channel}:{country}:{hash_bucket}` TTL 5min；rule 改动 invalidate pattern。

### 7.3 Play 渠道隔离（三道闸）
- **编译期**：Android productFlavors（gp / selfhosted）+ sourceset 分离，gp 包根本不打 SelfUpgradeManager 进去
- **运行时**：BuildConfig.CHANNEL == "gp" 直接不调升级 API
- **后端**：channel=gp 或 is_play_store=true 直接返 has_update:false

### 7.4 多租户隔离与 movie 接入
- movie 注册为 `cp_apps` 第一条，拿到 `tenant_uuid` + `api_key`
- movie App SDK 内置 `app_id=tenant_uuid` + HMAC secret
- movie-main 后端调 cp 走 `/api/v1/cp/...` + 服务端 API key（与 App 端 HMAC 不同）
- 未来抽离 cp 独立 ECS：只改 BASE_URL env，业务代码不动

---

## 8. VOD 与影视内容（A1' 方案）

### 8.1 角色分工
| 谁 | 登哪 | 干什么 |
|---|---|---|
| 技术运维（你+技术员） | 阿里云 RAM 子账号 → VOD 控制台 | 上传母片、转码模板、媒资批量管理 |
| 内容运营 | 自家后台 admin-web | **地区可见性矩阵** + **二次合规审核** + 上下架 + 推荐位 + 多语言标题 |

### 8.2 VOD ↔ 本地 DB 双轨同步
- **推送轨**：VOD MessageCallback → /internal/vod/webhook → 验签 → 更新本地 ct_videos 同步快照字段
- **拉取轨**：每天 03:00 celery-beat 跑 `sync_vod_metadata` 全量对账 + admin 手动 "Sync All" 按钮
- **每日 reconcile job**：调 VOD ListMedia API 全量 diff，输出"本地有 VOD 没"和"VOD 有本地没"两份告警
- **不一致兜底**：ct_videos.vod_status != ready 的影片，App 端列表自动过滤，避免 404

### 8.3 媒体提供商抽象层（避免 VOD 锁定）
- `app/shared/media_provider/protocol.py`：`IMediaProvider`, `IPlayTokenProvider` 接口
- `app/shared/media_provider/aliyun_vod.py`：当前实现
- 业务代码只调 `media_service.get_play_url(video_id, user_ip, user_id) -> PlayToken`
- 业务表字段命名 `vod_file_id` 不带 `aliyun_` 前缀；类型 varchar(128) 通用
- 未来切 Cloudflare Stream / Mux / 自建：换 adapter 不改业务

### 8.4 防盗链最小三件套
- HLS 加密 + 短期签名 URL（5-10min）+ UA/包签名校验
- Redis 单 IP 视频并发限流
- 不要自建 m3u8 代理（VOD 已做完）
- 不上 DRM Widevine（贵；起步用 HLS 加密 + 短签名 URL 扛着）

### 8.5 地区合规与二次审核
- ct_videos.secondary_review_status：draft / pending_review / approved / rejected
- ct_region_visibility：video × country 二维矩阵，默认 false
- 运营每入一条新片必须：① 二次审核通过 ② 逐国手动开启可见
- 中东禁酒/印尼涉赌/马来 LGBT/巴西禁毒等高敏感剧情接 ChatGPT/Gemini 摘要预审 + 标签

---

## 9. L4' 抽象层投资清单（day 1 必须做）

### 不做的（伪需求）
- ❌ region 分支 `if/else`
- ❌ 多 region DB 路由代码
- ❌ 跨区 cache invalidation 设计

### 要做的（真投资）
- ✅ **Repository 模式**：DB 访问全走 service 层，不裸调 ORM
- ✅ **cache_service 抽象**：Redis key 命名 `<module>:<resource>:<id>` 规范
- ✅ **时间戳全部 tz-aware**（ORM column `DateTime(timezone=True)`）
- ✅ **ID 用 snowflake/UUID 不用 auto_increment**（迁移 / 多 region 友好）
- ✅ **配置全 env 注入**：endpoint/region/bucket 名/JWT secret 都不写死
- ✅ **trace_id 透传**：FastAPI 中间件读 X-Request-Id（没有就生成 uuid7），contextvar 传到 logger/Sentry/Celery

---

## 10. 红线（任何代码 / 部署都不能违反）

### 致命级
1. keystore 不许进 Git；CI 只放 base64 secret；三地备份（1Password + 离线 GPG U 盘 + Play App Signing 托管）
2. **Play 包硬关自升级**（编译期 flavor 隔离 + 运行时不调 + 后端硬拒），不靠运行时判断
3. 视频不许明文 m3u8；HLS 加密 + 短期签名 + UA/包签名校验 + 并发限流
4. CDN/SMS/VOD 必须设月度上限 + 30/60/90% 告警 + 预付费；禁后付费裸奔
5. 手机 OTP 必须前置 Turnstile + 国家号段白名单 + 三层频控
6. **VOD ↔ 本地 reconcile 每日全量 job** 必须有
7. **/upgrade/check 必须 HMAC 签名**（防伪造 device_id 刷量）
8. **ct_region_visibility 默认 false**，运营必须手动开启每个国家可见性

### 严重级
9. **MySQL 必须用 RDS**，不许自建容器 MySQL
10. 任何 token / AK / 密钥不许进 Git；启用 secret scanning + push protection
11. ECS 必须每日快照 + 自动化重建脚本
12. 隐私政策 + App 内删除账号入口（Play 现在硬卡）
13. certbot 续签必须有健康检查
14. **import-linter CI 强制**模块边界（违反就 fail）
15. **media_provider 抽象层 day 1**，业务代码不直接读 vod_file_id
16. RAM 子账号 入职/离职/定期清理 SOP 必须写进 docs

---

## 11. 不做清单（防止范围蔓延）

- ❌ 不做微服务拆分（v1 单体多模块够）
- ❌ 不自建 Kafka/RabbitMQ（Redis 当 broker）
- ❌ 不自建 ELK（Sentry + OSS 归档）
- ❌ 不做读写分离 / 分库分表（DAU > 5w 再说）
- ❌ 不自建 CDN / 视频转码（VOD 全包）
- ❌ 不做实时推荐 / AI 算法（先类目 + 热度 + 二次审核标签排序）
- ❌ 不做多语言后台（中文一种）
- ❌ 不做自有支付通道（合规无底洞，先广告 + Play Billing）
- ❌ 不做 WebSocket / IM
- ❌ 不做 SSR 后台
- ❌ 不做 1080p/4K 视频
- ❌ 不做 DRM Widevine
- ❌ **不为不会发生的拆分付架构税**（不写事件总线、不写公共契约层 v2、不预先实现多 region 分支）
- ❌ **不在内容运营手里放 VOD 控制台权限**（运营只用自家后台）
- ❌ **不做 AB 面店铺状态联动灰度**（v1 用 device_id_hash_mod 做百分比灰度足矣；AB 面机制留 backlog）
- ❌ **不做付费会员业务**（required_tier 字段保留但默认全部 free；未来上 Play Billing 时再启用 VIP/SVIP 等级）

---

## 12. 阶段顺序（覆盖原版本）

- **P0** 账户域名云资源开通：基础设施账号 + 预算告警 + keystore 三地备份就位
- **P1** 仓库与骨架：monorepo + 模块化目录 + import-linter CI + 抽象层（repository / media_provider / cache_service / tz-aware / snowflake ID） + FastAPI/Vue3 hello world + RDS dev 库 + alembic 多 head + CI lint/test 通
- **P2 App 分发平台先 ship 上线**：channel_pack 模块完整实现（含多租户 cp_apps + 5 张表 + API + 规则引擎 + Walle 签名 + HMAC 校验 + admin 多页面） + ECS + nginx + certbot + Cloudflare（WAF + 海外套源） + Sentry + UptimeRobot + Telegram bot 告警全接通 → **第一次发版只发 cp 平台**，movie 是第一个租户，App 端只调 /upgrade/check
- **P3** user 模块：JWT + Email/Google/Phone OTP + Turnstile + 三层频控 + admin login（IP 白名单） → 第二次部署
- **P4** content 模块：categories + videos 业务表 + ct_region_visibility + VOD webhook + sync API + 地区可见性矩阵 + 二次审核流程 + admin 影片管理页 + 运营 RAM 子账号 SOP + media_provider 抽象层
- **P5** App 端播放链路：videos/{id}/play-token + watch-history + 视频鉴权中间件 + 海外套源验证 → 第三次部署（App 能播）
- **P6** 上线后红线兜底：CDN/SMS/VOD 上限告警 verify + ECS 快照 + Cloudflare 5xx 告警 + Sentry 通道接 Telegram + 隐私政策 + 删除账号入口 + operation_logs 全接通 + RAM 清理 SOP
- **P7** 增长期触发任务（DAU > 10w 才做）：印尼 PSE 注册 + 读写分离 + 多 region 评估 + K8s 迁移 + cp 模块抽离独立 ECS 评估

---

## 13. 沟通与文档要求

- **文档语言**：中文，部署/运维说明必须**大白话**，假设读者是 Android 出身、零运维经验
- **代码、标识符、commit message**：英文
- **注释**：默认不写。只在"为什么"非显然时写一行
- **响应风格**：简短、直接；关键决策给"推荐 + 一句理由"
- **部署文档**：每条 shell 命令带"这条命令在做什么"中文一句话注释

---

## 14. 红蓝对抗触发条件

遇到以下任一，**必须开 Agent 红蓝对抗**（一个架构师 + 一个预死亡分析师并行，再合稿）：
- 引入新依赖 / 新云服务 / 新数据库
- 改动数据模型核心表（特别是 cp_* 表）
- 切换部署形态（ECS → K8s、单 region → 多 region、cp 模块抽离）
- 涉及合规 / 支付 / 内容审核
- 任何"红线"清单里要破例的请求
- 任何"不做清单"里要做的请求

合稿格式：方案、风险、缓解、是否破例、用户拍板。

---

## 15. 任务清单 & 当前任务

完整可执行任务清单见 `/Users/yikong/Downloads/work/movie/TASKS.md`，按 P0–P7 阶段拆分，每条带复选框。

App 分发平台模块详细设计见 `/Users/yikong/Downloads/work/movie/docs/channel-module-design.md`。

Claude：每完成一条任务，立即把 `[ ]` 改成 `[✓]`，commit message 用 `done: P3.7 ...` 格式。

> 用户在这里写本次会话要做的具体任务编号（例如"做 P1.7-P1.12"或自由描述）：

**TASK**：
