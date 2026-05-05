# movie 任务清单（v2 红蓝二轮后定稿）

> PROMPT.md 阶段顺序的可执行细化版。每条都是**单次能完成的小任务**。
> 用 `[ ]` 表示未完成，`[✓]` 表示已完成，`[~]` 表示进行中，`[-]` 表示跳过/不做（后面用 `← 原因：...` 标注）。
>
> **协作约定**：
> - Claude 完成一条任务后，立即把 `[ ]` 改成 `[✓]` 并提交
> - 你手动完成的（买域名、注册账号、点控制台），自己改成 `[✓]`
> - 任何一条要跳过/延期，写明原因，**不静默删除**
> - 阶段顺序大体按 P0 → P7，但同阶段内可并行；标了 **依赖** 的必须先完成依赖项
> - commit message 用 `done: P2.7 cp_apps multi-tenant model` 格式

---

## 进度总览

- [ ] **P0 账户与域名**（19 条）— 全部待用户线下完成（注册账号/买域名/开服务）
- [✓] **P1 仓库 + 骨架 + 抽象层 day 1**（30 条）— **27/30 已完成 + 3 跳过**：1.1/1.2/1.4/1.6-1.28 全套（含 Dockerfile / 抽象层 6 件套 / trace_id+structlog / import-linter / GitHub CI / docker-compose.dev / alembic 多 head）；1.3 [-]文档暂不动 / 1.5 [-]仓库已存在 / 1.29 [-]依赖 0.2 阿里云账户
- [~] **P2 App 分发平台先 ship 上线**（44 条）⭐ 最大阶段 — **MVP 子集已完成 30/44**：5 个表 + HMAC + 规则引擎 + 全套 admin/cp API + 5 个 admin 页面 + 端到端验证；Celery/Redis/alembic/STS/CDN/单测 留待生产化
- [~] **P3 user 模块 + 第二次部署 + RBAC 6 模块**（20 条）— **MVP 子集已完成 17/20**：admin (3.3/3.4/3.12/3.13/3.14/3.14a/3.14b/3.14d) + user (3.1/3.5/3.6/3.7/3.8/3.9/3.10/3.11) + admin/users CRUD + 3.16 docs/api.md 自动导出；剩 3.2 alembic migration / 3.14c 权限管理页 / 3.15 第二次部署
- [ ] **P4 content 模块 + VOD 同步 + 地区可见性 + 二次审核**（20 条）
- [ ] **P5 App 端播放 + 首页聚合 + 搜索 + 第三次部署**（14 条）
- [ ] **P5+ 埋点 / 分析事件 / 后台仪表盘**（6 条）
- [ ] **P6 上线后红线兜底**（12 条）
- [ ] **P7 增长期触发任务**（6 条，DAU > 10w 才做）

---

## P0 账户与域名（你点控制台，Claude 帮不了）

- [ ] **0.1** 在 Cloudflare Registrar 或 Namecheap 买域名（**不要在阿里云国内买**）
- [ ] **0.2** 注册阿里云国际版账号（alibabacloud.com），完成实名/支付方式
- [ ] **0.3** 注册 Cloudflare 账号
- [ ] **0.4** 域名 NS 改到 Cloudflare（依赖 0.1 + 0.3）
- [ ] **0.5** 注册 GitHub 账号
- [ ] **0.6** 在 GitHub 创建私有仓库 `movie`
- [ ] **0.7** 仓库启用 secret scanning + push protection
- [ ] **0.8** 注册 Sentry（免费版）
- [ ] **0.9** 注册 UptimeRobot（免费版）
- [ ] **0.10** 注册 Telegram，建一个私有 bot（@BotFather），拿 token；建一个 channel 接告警
- [ ] **0.11** Google Cloud Console 创建 OAuth Client ID（Web + Android 两份）
- [ ] **0.12** 注册 Twilio 或开通阿里云国际短信；**充值后立刻设上限**
- [ ] **0.13** 注册 1Password 团队版（keystore + 所有凭据备份用）
- [ ] **0.14** 阿里云国际版账户级**月度预算告警**：30/60/90% 三档
- [ ] **0.15** OSS / CDN / VOD 各自的**流量/费用上限 + 告警** + 预付费
- [ ] **0.16** SMS 账户**预付费**模式（**禁止后付费**），余额低告警
- [ ] **0.17** 注册 Termly（或同类）生成隐私政策 + 服务条款模板
- [ ] **0.18** 把以上所有账号密码 / API key / recovery code 存进 1Password
- [ ] **0.19** 写 `docs/account-list.md`（所有云资源 / 账号 / URL 一览，**不写密码**）

---

## P1 仓库 + 骨架 + 抽象层 day 1

### 1A 仓库初始化
- [✓] **1.1** `git init` + 写 `.gitignore`（python、node、env、IDE、*.keystore、*.jks、_*.db）
- [✓] **1.2** 创建顶层目录：`backend/ admin-web/ infra/ docs/ scripts/ .github/workflows/`（infra/ scripts/ .github/ 随后续任务陆续创建）
- [-] **1.3** Review/调整已生成的 `README.md` 和 `PROMPT.md`、`TASKS.md` ← 原因：本批次不动文档，后续 docs/api.md 一并修订
- [✓] **1.4** 写 `.editorconfig`
- [-] **1.5** 第一次 `git push` 到 GitHub（依赖 0.6） ← 原因：仓库已存在并有提交（fc44623），等价完成

### 1B backend 骨架
- [✓] **1.6** `backend/pyproject.toml`（用 uv，Python 3.12+）
- [✓] **1.7** 安装依赖（MVP 子集：fastapi, uvicorn, sqlalchemy, pydantic-settings, pyjwt, bcrypt, email-validator；后续按需补 alembic/celery/redis/structlog/sentry/import-linter）
- [✓] **1.8** 模块化目录创建：`backend/app/{core,shared,modules/{channel_pack,user,content,admin},adapters,api}/`
- [✓] **1.9** `backend/app/main.py` hello world + `/healthz` + `/readyz`
- [✓] **1.10** `backend/app/core/config.py` 用 pydantic-settings 读 env（**禁止 os.getenv 散落**）
- [✓] **1.11** `backend/Dockerfile`（多阶段，非 root UID 1000，distroless 或 python-slim）

### 1C 抽象层 day 1（L4'）
- [✓] **1.12** `backend/app/shared/repository_base.py`：Repository 模式基类
- [✓] **1.13** `backend/app/shared/cache_service.py`：Redis key 命名规范 `<module>:<resource>:<id>` + invalidate_pattern
- [✓] **1.14** `backend/app/core/clock.py`：tz-aware now() 接口（IClock，方便测试）
- [✓] **1.15** `backend/app/core/ids.py`：snowflake/uuid7 ID 生成
- [✓] **1.16** `backend/app/shared/media_provider/protocol.py`：IMediaProvider, IPlayTokenProvider 接口（占位，实现 P4 写）
- [✓] **1.17** `backend/app/core/security_protocol.py`：IAuthGuard 接口（user 模块实现）
- [✓] **1.18** `backend/app/shared/middleware/trace_id.py`：FastAPI 中间件读/生成 X-Request-Id，contextvar 透传到 logger/Sentry
- [✓] **1.19** structlog JSON 输出 + 标准字段（ts, level, logger, trace_id, module, event）

### 1D 模块边界 CI 强制
- [✓] **1.20** `.importlinter` 配置：channel_pack 不许 import user/content/admin；横切关注点必须经 app.core 或 app.shared（含身份层临时豁免，待抽 identity 模块后移除）
- [✓] **1.21** `.github/workflows/ci.yml`：跑 ruff + mypy + pytest + **import-linter** + admin-web pnpm build；mypy 渐进开严先 continue-on-error

### 1E admin-web 骨架（部分由 nextstream/admin 搬迁，见 docs/admin-migration.md）
- [✓] **1.22** 从 `/Users/yikong/Downloads/nextstream/admin/` 搬迁基础骨架到 `admin-web/`（package.json / vite.config / tsconfig / Layout / Login / icons），并删除 nextstream 自带的业务 stores 与 views
- [✓] **1.23** 重组 `admin-web/src/modules/{channel-pack,content,user,admin}/{views,api,stores,types}/` 模块化目录
- [✓] **1.24** 重写 API 客户端：BASE_URL 指 FastAPI（/api/v1）、改 token key 为 `mv_admin_token` / `mv_admin_refresh`、适配 FastAPI `detail` 错误字段
- [✓] **1.25** Placeholder 页面已有，已与 backend 联通（curl + 浏览器登录均通过）
- [✓] **1.26** admin-web build & dev 已跑通（pnpm dev 监听 :5174，已验证登录链路）

### 1F 本地编排 + RDS + Alembic 多 head
- [✓] **1.27** `infra/docker-compose.dev.yml`（fastapi + redis；MySQL 用 RDS 不用本地）
- [✓] **1.28** `backend/.env.example`（MVP 版：DATABASE_URL / JWT_SECRET / SEED_* / CORS_*）
- [-] **1.29** 在阿里云开通 RDS for MySQL 8.0 ← 原因：依赖 0.2 阿里云国际版账号（用户线下做）；当前用 SQLite，alembic 配置已就位待切
- [✓] **1.30** **alembic init + 配 multi-head**（4 个目录：channel_pack/user/content/admin）— alembic.ini + env.py + script.py.mako + README 已就位；MVP 仍用 `Base.metadata.create_all`，schema 演化时切到 alembic

---

## P2 App 分发平台先 ship 上线 ⭐ 重头戏

### 2A channel_pack 数据模型 + Migration
- [✓] **2.1** `cp_apps` 模型（多租户根：tenant_uuid + api_key_hash + hmac_secret + owner_admin_user_id）
- [✓] **2.2** `cp_channels` 模型（app_id FK + is_play_store + signing_strategy + UniqueConstraint(app_id, code)）
- [✓] **2.3** `cp_app_versions` 模型（app_id + status state machine + UniqueConstraint(app_id, version_code)）
- [✓] **2.4** `cp_upgrade_rules` 模型（target + policy + popup_strategy enum + 4 个 i18n 多语言文案字段）
- [✓] **2.5** `cp_apk_signing_jobs` 模型（含 idempotency_key unique 索引 + cdn_warmup_status）
- [ ] **2.6** alembic migration — MVP 用 `Base.metadata.create_all`；schema 演化时补 alembic multi-head

### 2B HMAC 签名 + 多租户中间件
- [✓] **2.7** `services/hmac_verifier.py`：HMAC-SHA256 + 5min replay 防御 + 常数时间比较
- [✓] **2.8** `services/app_registry.py`：tenant_uuid → cp_apps 加载 + 进程内 60s 缓存（生产换 Redis）
- [✓] **2.9** /upgrade/check 内联 HMAC 校验（功能等价；将来抽 Depends 复用更多公开端点）

### 2C 升级规则引擎（核心算法）
- [✓] **2.10** `services/upgrade_engine.py`：纯函数实现规则匹配 + 优先级 + crc32 灰度 + debug_steps
- [ ] **2.11** Redis 缓存 — MVP 进程内字典；DAU 起来前补 Redis（接口已抽象）
- [ ] **2.12** Cache invalidate pattern — 进程内单 key invalidate 已实现；Redis 化时补 pattern
- [ ] **2.13** 单测 — MVP 用 `scripts/cp_test_client.py` 端到端 4 场景验证（升级命中 / 已是最新 / Play 硬拒 / HMAC 错），单元测试待补
- [✓] **2.14** Play 渠道后端硬拒（is_play_store=true → has_update:false，不查规则）

### 2D Walle 渠道签名工作流
- [✓] **2.14a** version_code 严格递增校验（重复或回退直接 400）
- [✓] **2.15** `adapters/walle.py`：IChannelSigner 接口 + WalleStubSigner（MVP 占位）+ WalleCliSigner（生产 stub）
- [✓] **2.16** `adapters/object_store.py`：IObjectStore 接口 + LocalFSObjectStore（MVP）；生产换 OSS 实现同接口
- [ ] **2.17** CDN refresh/preheat — MVP 走 FastAPI StaticFiles 不需要预热；生产 OSS+CDN 时补
- [✓] **2.18** `services/signing_service.py`：finalize 时 fan-out 创建 jobs + 幂等性（同 idempotency_key 已 success 直接复用）
- [ ] **2.19** Celery 异步 — MVP 用 FastAPI BackgroundTasks 同进程跑（接口对齐，将来切 Celery 改 task 装饰器）
- [✓] **2.20** 任务流：OSS 下母包 → walle 注入 → SHA256 → 上 OSS → 写回 DB → 自动判定 version=ready
- [ ] **2.21** 单测 — 同 2.13，端到端覆盖

### 2E 公开 API
- [✓] **2.22** `GET /api/v1/cp/upgrade/check`：HMAC 校验 + 时间戳防 replay + 规则引擎 + i18n 文案按 country 选语言
- [ ] **2.23** `GET /cp/apk/{channel_code}/{version_code}` 302 跳 CDN — MVP 直接 download_url 走 /storage/；生产 CDN 签名 URL 时补
- [✓] **2.24** `GET /api/v1/cp/healthz`

### 2F 后台 API
- [✓] **2.25** `/admin/cp/apps` CRUD + 一次性返回 api_key + hmac_secret + 重生密钥端点（仅超管可建/删）
- [✓] **2.26** `/admin/cp/apps/{app_id}/channels` CRUD（含 code 格式校验）
- [✓] **2.27** `/admin/cp/apps/{app_id}/versions` CRUD（multipart 直传 + version_code 严格递增校验）
- [ ] **2.28** OSS STS 直传凭证 — MVP multipart 直传后端，生产用 OSS STS（管理员上传 50MB+ 时绕过 ECS 出口带宽）
- [✓] **2.29** `versions/{id}/finalize` 触发 fan-out 签名（BackgroundTasks）
- [✓] **2.30** `/admin/cp/apps/{app_id}/rules` CRUD（含 popup_strategy + 4 个 i18n 文案 + 灰度区间 + 优先级 + 生效窗）
- [✓] **2.31** `rules/preview` 输入 sample 设备 → 返回命中规则 + debug_steps（运营调试用）
- [✓] **2.32** `signing-jobs` 列表 + 状态过滤 + 手动 retry

### 2G admin-web 渠道包页面
- [✓] **2.33** 登录页（之前 P3.13 已完成）
- [✓] **2.34** App 租户管理页（仅超管可见 + 一次性密钥显示对话框 + 重生密钥 + 选为当前）
- [✓] **2.35** 渠道管理页（含 Play 渠道警告标识）
- [✓] **2.36** APK 母包上传页（XHR 进度条 + 多语言 changelog 编辑 + Finalize 按钮）
- [✓] **2.37** 升级规则配置页（含规则预览 + 灰度区间显示百分比 + popup_strategy + 4 个 i18n 文案 tab）
- [✓] **2.38** 签名 job 状态页（按 vc/status 过滤 + 失败手动 retry）

### 2H 部署基础设施一次性配齐（B3 重要：避免双部署精力撕裂）
- [ ] **2.39** 阿里云国际版采购 ECS（新加坡 region，4C8G，按量起步）+ 安全组 + Docker 安装
- [ ] **2.40** `infra/docker-compose.yml`（生产）+ `scripts/deploy.sh`（拉镜像 → up -d → 健康检查）
- [ ] **2.41** `.github/workflows/deploy.yml`：push main → build & push 镜像到阿里云 ACR → SSH → deploy.sh
- [ ] **2.42** 域名 A 记录 → ECS（Cloudflare Proxy 先关，certbot 拿证书后再开）+ certbot 拿 Let's Encrypt 证书 + nginx HTTPS + HSTS + 续签 cron + 续签健康检查 + Cloudflare Proxy 打开 + WAF 规则 + Cloudflare 海外流量套源 + Sentry SDK 接入 + UptimeRobot 5 监控点 + Telegram bot 告警通道（Sentry/UptimeRobot/CloudMonitor 全接 Telegram）+ 阿里云 CloudMonitor 5 条告警 + ECS 每日快照计划 + `scripts/restore.sh` + 写 `docs/deploy.md`（大白话每行命令带中文注释）+ 写 `docs/runbook.md`（常见故障）+ **完整 staging 演练（创建 movie 租户、上传 APK、签名、check 接口验证）→ 第一次正式发版（仅 cp 平台）**

---

## P3 user 模块 + 第二次部署

### 3A 数据模型
- [✓] **3.1** SQLAlchemy 模型：u_users（含 app_id FK + country/preferred_language）, u_user_oauth, u_devices, u_otp_codes, u_refresh_tokens
- [ ] **3.2** alembic migration — MVP 用 create_all；schema 演化时补

### 3B 认证
- [✓] **3.3** `app/core/security.py`：JWT access 15m + refresh 30d + scope=admin/user/admin_refresh/user_refresh + jti
- [✓] **3.4** Depends：JWT 校验 + scope 校验（admin / user / user_refresh）；refresh 黑名单 MVP 进程内（生产换 Redis）
- [✓] **3.5** `POST /api/v1/auth/email/register` + `/email/login`（密码 bcrypt + 强度校验）
- [✓] **3.6** `POST /api/v1/auth/google`（mock：GOOGLE_CLIENT_ID 未设接受任何 id_token；生产 google-auth 验签）
- [✓] **3.7** Cloudflare Turnstile 服务端校验工具（mock：TURNSTILE_SECRET 未设 dev mode 接受所有 token）
- [✓] **3.8** `POST /api/v1/auth/phone/send-otp`：Turnstile + 三层频控（号 60s / IP 5min/5 次 / 设备 10 次/天）+ 国家号段白名单（C1+C3 区域）+ mock SMS 进 log
- [✓] **3.9** `POST /api/v1/auth/phone/verify`：6 位码 bcrypt 校验 + 5 次错作废
- [✓] **3.10** `POST /api/v1/auth/refresh`：旋转 access+refresh + 旧 refresh 入黑名单（DB + 进程内）
- [✓] **3.11** `POST /api/v1/devices/register`：设备指纹 + 渠道 + last_seen_at（同 user+device+app 唯一）

### 3C admin 鉴权 + RBAC（增强版：6 模块 × view/edit 权限点 + 4 seed 角色）
- [✓] **3.12** a_admin_users + a_admin_roles 模型（含 app_scope 多租户字段）；a_operation_logs 待补
- [✓] **3.13** `POST /api/v1/admin/auth/login` + `GET /admin/auth/me`（IP 白名单 / 改密二次校验留待生产前补）
- [✓] **3.14** admin RBAC 中间件（按 app_scope 限制 cp_apps 数据；user 资源走 admin scope；细粒度授权 MVP 走 super_admin 短路 + scope 校验）
- [✓] **3.14a** RBAC 权限树定义：6 大模块（dashboard / cp / content / user / membership / permissions），扁平化字符串权限存于 a_admin_roles.permissions
- [✓] **3.14b** 4 个 seed 角色：Super_Admin（is_super_admin=true 短路所有检查）/ Content_Manager / Global_Ops / Service_Auditor（只读）
- [✓] **3.14d** 前端路由 / 组件级 v-if 权限校验（router beforeEach + auth.hasPermission 已落地）
- [ ] **3.14c** admin-web 权限管理页（角色 CRUD + 权限矩阵勾选 + 成员分配）

### 3D 部署
- [ ] **3.15** 第二次部署：通过 GitHub Actions 自动部署（依赖 P2.41）
- [✓] **3.16** docs/api.md 用 FastAPI OpenAPI 自动导出（`backend/scripts/export_api_docs.py`，37 端点 / 7 tag 分组；改路由后重跑刷新）

---

## P4 content 模块 + VOD 同步 + 地区可见性 + 二次审核

### 4A VOD 控制台开通 + RAM
- [ ] **4.1** 阿里云国际版开通 VOD（ap-southeast-1 区）
- [ ] **4.2** VOD 控制台配转码模板：**仅 480p + 720p**（不开 1080p/4K）
- [ ] **4.3** RAM 子账号策略 `MovieVodOps`（运营登 VOD 控制台用，含 MFA + ActionTrail 投递 OSS）
- [ ] **4.4** RAM 角色 `MovieBackendVodReader`（后端用，仅 GetVideoInfo / GetPlayInfo / SearchMedia）
- [ ] **4.5** 写 `docs/ram-account-sop.md`（入职/离职/定期清理 SOP，含 external_identity 表绑定流程）
- [ ] **4.6** 写 `docs/vod-console-guide.md`（VOD 控制台中英操作手册）

### 4B 数据模型
- [ ] **4.7** SQLAlchemy 模型：ct_categories（i18n）, **ct_videos（标准字段：code 业务编码 / title_i18n / description_i18n / type / category_id / tags / score / rating / release_year / release_date / duration_min / director / cast_list / studio / cover_url / poster_url / trailer_url / vod_file_id + 同步快照 + required_tier(占位) / status / secondary_review_status / featured(bool) / trending(bool) / views / recommend_priority）**, ct_video_episodes（含 season/episode_no/duration_min/vod_file_id）, ct_watch_history（user_id, video_id, episode_id, position_sec, duration_sec, updated_at）, **ct_region_visibility**（video × country 矩阵）
- [ ] **4.8** alembic migration（content 子目录）

### 4C media_provider 抽象层（A1' 落地）
- [ ] **4.9** `app/shared/media_provider/aliyun_vod.py`：实现 IMediaProvider + IPlayTokenProvider
- [ ] **4.10** Wire-up：`media_service` 依赖注入；业务代码只用 service 不直接读 vod_file_id

### 4D VOD ↔ 本地同步双轨
- [ ] **4.11** `POST /internal/vod/webhook`：验签 + 处理 FileUploadComplete / TranscodeComplete / FileDeleted 事件
- [ ] **4.12** Celery 任务 `sync_vod_metadata`：每天 03:00 全量 diff（拉 ListMedia API 分页）
- [ ] **4.13** **每日 reconcile job**：对账输出"本地有 VOD 没"和"VOD 有本地没"两份告警进 Telegram
- [ ] **4.14** admin 手动 "Sync All" 按钮 + 单条 "Pull from VOD" 按钮

### 4E 后台业务字段 + 地区可见性 + 二次审核
- [ ] **4.15** `POST /api/v1/admin/content/videos`（创建影片业务记录，绑 vod_file_id）
- [ ] **4.16** `PUT /api/v1/admin/content/videos/{id}`（编辑业务字段 + 多语言标题/描述）
- [ ] **4.17** `POST /api/v1/admin/content/videos/{id}/region-visibility`（地区可见性矩阵编辑：video × country 二维勾选）
- [ ] **4.18** `POST /api/v1/admin/content/videos/{id}/secondary-review`（二次审核流转：draft → pending → approved/rejected）
- [ ] **4.19** admin-web 影片管理页（列表 + 编辑 + 同步状态 + 地区可见性矩阵 + 二次审核流转）
- [ ] **4.20** admin-web 分类管理页（i18n 多语言名）

---

## P5 App 端播放 + 第三次部署

### 5A App 端 API
- [ ] **5.1** `GET /api/v1/videos`（列表，分页，按用户 country 过滤 ct_region_visibility + secondary_review_status=approved + vod_status=ready）
- [ ] **5.2** `GET /api/v1/videos/{id}`
- [ ] **5.3** `GET /api/v1/videos/{id}/play-token`（调 media_service 拿 PlayToken；5min 过期 + IP 绑定）
- [ ] **5.3a** **`GET /api/v1/videos/home` 首页聚合接口**（返回 featured + continueWatching + trending + top10，单接口减 App 往返）
- [ ] **5.3b** `GET /api/v1/videos/search?q=`（按 title / director / cast / tags 多字段检索）

### 5B 防盗链
- [ ] **5.4** UA / 包签名 header 校验中间件
- [ ] **5.5** Redis 单 IP 视频并发限流
- [ ] **5.6** Cloudflare 海外流量套源验证（实测 SEA + 中东 + 拉美 + 非洲 TTFB）

### 5C 观看历史
- [ ] **5.7** `POST /api/v1/watch-history`（保留每用户最近 200 条，超出删旧）

### 5D 部署 + 测试
- [ ] **5.8** 第三次部署（通过 GitHub Actions）
- [ ] **5.9** 端到端测试：用户注册登录 → 列表 → 播放 token → 实际播放
- [ ] **5.10** 中东节点 / 拉美节点 / 非洲节点 实测起播延迟（webpagetest）
- [ ] **5.11** 隐私政策 + 服务条款上线（依赖 0.17 Termly）
- [ ] **5.12** App 内"删除账号"接口 `POST /api/v1/users/me/delete-request`（Play 强制）

---

## P5+ 埋点 / 仪表盘（与 P5 并行）

### 5E 埋点 / 分析事件
- [ ] **5.13** s_analytics_events 表 + migration（按 event_type/page_code/created_at 加索引）
- [ ] **5.14** `POST /api/v1/analytics/track`（公开 + optionalAuth，事件类型枚举校验，限流防刷）
- [ ] **5.15** App / admin-web 客户端埋点封装（page_view + play_start/complete + search + upgrade_check + ad_*）

### 5F 后台仪表盘
- [ ] **5.16** `GET /api/v1/admin/stats/overview`（DAU / 新订阅 / 收入 / 广告 PV，从 s_analytics_events 聚合）
- [ ] **5.17** `GET /api/v1/admin/stats/trends`（30 天趋势 + 留存曲线 + 广告位分布）
- [ ] **5.18** admin-web 仪表盘 4 KPI 卡 + 4 ECharts 图

---

## P6 上线后红线兜底

- [ ] **6.1** Sentry 错误告警通道接 Telegram + 邮箱
- [ ] **6.2** OSS / CDN / VOD / SMS 全部预付费 + 上限 + 告警 已配齐 verify
- [ ] **6.3** GitHub Actions secrets 审计 + 历史 commit 扫描无明文密钥
- [ ] **6.4** ECS docker logs 配 `max-size=100m max-file=3`
- [ ] **6.5** Redis 容器关闭 AOF（确认数据可丢）
- [ ] **6.6** RDS 自动备份 + 跨区快照 已开启 verify
- [ ] **6.7** Cloudflare 5xx 告警规则
- [ ] **6.8** keystore 三地备份完成（1Password + 离线 GPG U 盘 + Play App Signing 托管）
- [ ] **6.9** RAM 子账号清理 SOP 演练（建一个 → 离职模拟 → 同步禁用）
- [ ] **6.10** **HMAC 签名密钥轮换演练**（cp_apps.api_key_hash 改密 + App SDK 平滑过渡）
- [ ] **6.11** 完整压测（Locust 1000 并发打 /upgrade/check + /videos）
- [ ] **6.12** 写 `docs/incident-playbook.md`（故障应急手册：DB 挂 / CDN 挂 / VOD 挂 / 域名挂 / Cloudflare 挂）

---

## P7 增长期触发任务（DAU > 10w 才做，**现在不做**）

- [ ] **7.1** 印尼 PSE 注册（Kominfo）
- [ ] **7.2** RDS 升级规格 + 读写分离评估
- [ ] **7.3** LATAM/非洲 流量切到 Cloudflare CDN 评估
- [ ] **7.4** 多 region 部署评估（API 多 region + 数据库主从）
- [ ] **7.5** K8s 迁移评估（ACK 托管版）
- [ ] **7.6** **cp 模块抽离独立 ECS / 独立 RDS schema** 评估（如果接了第二个 App）
