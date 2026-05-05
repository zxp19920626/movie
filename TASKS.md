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
- [✓] **P1 仓库 + 骨架 + 抽象层 day 1**（30 条）— **27/30 已完成 + 3 跳过**
- [~] **P2 App 分发平台**（44 条）⭐ — **38/44**：2.11/2.12/2.13/2.19/2.21/2.23 含；剩 6 项 = 2.6 alembic[-暂缓] / 2.17 CDN / 2.28 OSS STS / 2.39-2.42 部署链（全部依赖 P0）
- [~] **P3 user 模块 + 部署 + RBAC**（20 条）— **18/20**；剩 3.2 alembic[-暂缓] / 3.15 部署[依赖 P2.41]
- [~] **P4 content + VOD + 地区可见性 + 二次审核**（20 条）— **13/20**：模型 + media_provider + admin API + admin-web + VOD 同步骨架 + admin 触发按钮；剩 4.1-4.6 VOD 控制台[依赖 P0] / 4.8 alembic[-暂缓]
- [~] **P5 App 端播放 + 首页 + 搜索 + 部署**（14 条）— **9/14**：5.1/5.2/5.3/5.3a/5.3b/5.4/5.5/5.7/5.12；剩 5.6/5.8/5.9/5.10/5.11 依赖 P0 + 部署链
- [~] **P5+ 埋点 / 仪表盘**（6 条）— **5/6**；剩 5.15 客户端封装（admin 部分等业务页面铺开）
- [~] **P6 上线后红线兜底**（12 条）— **5/12**：6.3 secrets 扫描 / 6.4 docker logs / 6.10 HMAC 轮换 / 6.11 Locust / 6.12 应急手册；剩 7 项依赖 P0 监控告警账户
- [ ] **P7 增长期触发任务**（6 条，DAU > 10w 才做）

**总进度：约 110/157 = 70%**（剩余 47 项中 ≈40 项硬卡 P0 用户账户线下完成）

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
- [-] **2.6** alembic migration ← 原因：alembic 配置已就位（P1.30），但首条迁移最好基于生产 RDS 真实 schema 生成；当前 dev 用 create_all 充足，留待生产前一刻补

### 2B HMAC 签名 + 多租户中间件
- [✓] **2.7** `services/hmac_verifier.py`：HMAC-SHA256 + 5min replay 防御 + 常数时间比较
- [✓] **2.8** `services/app_registry.py`：tenant_uuid → cp_apps 加载 + 进程内 60s 缓存（生产换 Redis）
- [✓] **2.9** /upgrade/check 内联 HMAC 校验（功能等价；将来抽 Depends 复用更多公开端点）

### 2C 升级规则引擎（核心算法）
- [✓] **2.10** `services/upgrade_engine.py`：纯函数实现规则匹配 + 优先级 + crc32 灰度 + debug_steps
- [✓] **2.11** RedisCacheService 实现（懒加载 redis-py + JSON 序列化 + key_prefix）；configure_default_cache(REDIS_URL) 一行切换
- [✓] **2.12** invalidate_pattern：进程内 fnmatch / Redis SCAN+UNLINK 双实现，对齐 ICacheService 契约
- [✓] **2.13** 单测 — `tests/test_hmac_verifier.py` (15 tests) + `test_upgrade_engine.py` (13 tests) + `test_signing_service.py` (6 tests) = 34 passed
- [✓] **2.14** Play 渠道后端硬拒（is_play_store=true → has_update:false，不查规则）

### 2D Walle 渠道签名工作流
- [✓] **2.14a** version_code 严格递增校验（重复或回退直接 400）
- [✓] **2.15** `adapters/walle.py`：IChannelSigner 接口 + WalleStubSigner（MVP 占位）+ WalleCliSigner（生产 stub）
- [✓] **2.16** `adapters/object_store.py`：IObjectStore 接口 + LocalFSObjectStore（MVP）；生产换 OSS 实现同接口
- [ ] **2.17** CDN refresh/preheat — MVP 走 FastAPI StaticFiles 不需要预热；生产 OSS+CDN 时补
- [✓] **2.18** `services/signing_service.py`：finalize 时 fan-out 创建 jobs + 幂等性（同 idempotency_key 已 success 直接复用）
- [✓] **2.19** backend/app/celery_app.py：可选 Celery 入口（CELERY_BROKER_URL 配则启用）+ docker-compose.prod.yml 加 worker 服务（profile=celery 默认不拉起）；当前仍以 BackgroundTasks 为默认路径，迁移路径文档化
- [✓] **2.20** 任务流：OSS 下母包 → walle 注入 → SHA256 → 上 OSS → 写回 DB → 自动判定 version=ready
- [✓] **2.21** 单测 — 同 2.13 一并覆盖（signing_service fan-out 幂等 + check_and_mark_ready 状态机）

### 2E 公开 API
- [✓] **2.22** `GET /api/v1/cp/upgrade/check`：HMAC 校验 + 时间戳防 replay + 规则引擎 + i18n 文案按 country 选语言
- [✓] **2.23** `GET /cp/apk/{tenant_uuid}/{channel_code}/{version_code}` 302 跳 storage URL（HMAC + ts 防盗链）；生产 CDN 化时改 object_store.public_url 一处
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
- [-] **3.2** alembic migration ← 原因：同 2.6，等生产 RDS 上线前一刻基于真实 schema 生成首条迁移

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
- [✓] **3.14c** admin-web 权限管理页：
        - backend：admin/permissions.py（6 模块 × 多权限点 + 4 seed 角色定义）+ admin/rbac_routers.py（roles CRUD + admin-users CRUD + permission tree GET）
        - frontend：RolesView（角色列表 + 权限矩阵勾选含模块全选）+ AdminsView（管理员 CRUD + 角色分配 + app_scope 多租户隔离 + 软删 suspended）
        - 状态机：super_admin 短路 + 内置角色不可删 + 删除前校验是否仍有用户绑定 + 自禁锁防 lockout

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
- [✓] **4.7** SQLAlchemy 模型：ct_categories / ct_videos（含全套业务字段 + 二审 + 推荐位 + VOD 快照）/ ct_video_episodes / ct_watch_history / ct_region_visibility 5 张表全部就位
- [-] **4.8** alembic migration（content 子目录）← 原因：同 2.6 / 3.2，alembic 配置已就位，首迁待生产 RDS 上线时一并生成

### 4C media_provider 抽象层（A1' 落地）
- [✓] **4.9** `app/shared/media_provider/aliyun_vod.py`：AliyunVodProvider + AliyunPlayTokenProvider stub（issue_play_token 返 stub PlayToken 让业务可拼通；P4 接 SDK 后替换 _ensure_client 即可）
- [✓] **4.10** `media_provider/service.py`：configure_default_providers / get_media_provider / get_play_token_provider；main.py lifespan 启动时调；测试可 set_*_provider 注入 fake

### 4D VOD ↔ 本地同步双轨
- [✓] **4.11** `POST /internal/vod/webhook`：HMAC-SHA256 验签（VOD_WEBHOOK_SECRET 配则强制；空则 dev 放行）+ 处理 FileUploadComplete/TranscodeComplete/FileDeleted
- [✓] **4.12** sync_vod_metadata：拉 list_media 分页 → 增量更新 ct_videos.vod_status / vod_synced_at；当前 SDK stub 抛 NotImplementedError 被 catch；接 SDK 后无需改逻辑
- [✓] **4.13** reconcile_videos_against_vod：返回 missing_remote / extra_remote 两份列表；POST /admin/content/vod/reconcile 触发；接入告警通道时 wire 到 Telegram
- [✓] **4.14** admin-web VideosView 加 Sync All / 对账 / 单行同步按钮（stub 模式提示 + 真模式刷状态）

### 4E 后台业务字段 + 地区可见性 + 二次审核
- [✓] **4.15** `POST /api/v1/admin/content/videos`（含 code 唯一 / category_id 校验 / vod_file_id）
- [✓] **4.16** `PUT /api/v1/admin/content/videos/{id}`（含状态机：online 必须 approved）
- [✓] **4.17** `POST /api/v1/admin/content/videos/{id}/region-visibility`（整批替换语义 + 黑名单制）
- [✓] **4.18** `POST /api/v1/admin/content/videos/{id}/secondary-review`（draft↔pending↔approved/rejected 状态机）
- [✓] **4.19** admin-web VideosView：列表 + 4 tab 编辑（基础/i18n/资源-VOD/上下线-推荐）+ 地区可见性矩阵勾选 + 二审下拉 submit/approve/reject + VOD 状态/二审状态/推荐位标签
- [✓] **4.20** admin-web CategoriesView：列表 + 多语言名编辑（9 lang）+ 父子分类 + 软删归档

附加：categories CRUD（`/admin/content/categories` GET/POST/PATCH/DELETE）一并落地，支持 4.20 后台联调

---

## P5 App 端播放 + 第三次部署

### 5A App 端 API
- [✓] **5.1** `GET /api/v1/videos`（按 user.country 过滤 region_visibility + status/review/vod_status 三重门 + 分类/类型筛选）
- [✓] **5.2** `GET /api/v1/videos/{id}`（不可见返 404 而非 403，避免泄露存在性）
- [✓] **5.3** `GET /api/v1/videos/{id}/play-token`（5min TTL + IP 绑定 + 调 IPlayTokenProvider stub；P5+ 接订阅后加 required_tier 校验）
- [✓] **5.3a** `GET /api/v1/videos/home` 首页聚合：featured + continueWatching + trending + top10 单接口
- [✓] **5.3b** `GET /api/v1/videos/search?q=` 多字段检索：code/director/studio/cast/tags/title_i18n/description_i18n（SQLite ilike + JSON 文本兜底；MySQL 上线后换 JSON_CONTAINS / 全文索引）

### 5B 防盗链
- [✓] **5.4** shared/middleware/app_sign.py：X-App-Ts + X-App-Sig (HMAC-SHA256(secret, "ts|UA")) 校验；整组 /videos/* 强制；APP_SIGN_SECRET 留空 dev 模式自动放行；±5min skew 容忍
- [✓] **5.5** rate_limit FastAPI Depends 工厂 + ICacheService.incr 抽象（Redis INCR+EXPIRE / 内存原子加 + TTL）；play-token 30/min、search 60/min；X-RateLimit-* 响应头
- [ ] **5.6** Cloudflare 海外流量套源验证（实测 SEA + 中东 + 拉美 + 非洲 TTFB）

### 5C 观看历史
- [✓] **5.7** watch-history POST/GET/DELETE：upsert (user_id, video_id, episode_id) + 自动 prune 保留每用户最近 200 条

### 5D 部署 + 测试
- [ ] **5.8** 第三次部署（通过 GitHub Actions）
- [ ] **5.9** 端到端测试：用户注册登录 → 列表 → 播放 token → 实际播放
- [ ] **5.10** 中东节点 / 拉美节点 / 非洲节点 实测起播延迟（webpagetest）
- [ ] **5.11** 隐私政策 + 服务条款上线（依赖 0.17 Termly）
- [✓] **5.12** `POST /api/v1/users/me/delete-request`（confirm=true + 软删 status=deleted + 撤销所有 RefreshToken；30 天后异步 PII 真清留 TODO）

---

## P5+ 埋点 / 仪表盘（与 P5 并行）

### 5E 埋点 / 分析事件
- [✓] **5.13** s_analytics_events 表（4 个 composite index：type+time / user+time / app+time / page+time；行级追加只插不更）
- [✓] **5.14** `POST /api/v1/analytics/track`：公开 + optionalAuth + 16 种事件类型白名单 + 100/min/IP 限流 + 单条/批量（最多 50）
- [-] **5.15** App / admin-web 客户端埋点封装 ← 原因：admin-web 部分等业务页面铺开后再加；App 部分由 App 团队接

### 5F 后台仪表盘
- [✓] **5.16** `GET /admin/stats/overview`：DAU/DAA/play_start/search/ad_pv/upgrade_check（subscriptions/revenue 占位待 P5+ 订阅模块）
- [✓] **5.17** `GET /admin/stats/trends`：日粒度 trend；4 个 series（play_start/search/upgrade_check/ad_pv）；zero-fill 不断点
- [✓] **5.18** admin-web DashboardView：6 KPI 卡（含 DAU/DAA）+ 4 ECharts line 图 + period 切换（24h/7d/30d）+ trend 切换（7/14/30/90d）

---

## P6 上线后红线兜底

- [ ] **6.1** Sentry 错误告警通道接 Telegram + 邮箱
- [ ] **6.2** OSS / CDN / VOD / SMS 全部预付费 + 上限 + 告警 已配齐 verify
- [✓] **6.3** .github/workflows/secrets-scan.yml（gitleaks 全 history）+ .gitleaks.toml（项目级豁免：dev 占位 secret / 文档示例 / 测试夹具）
- [✓] **6.4** infra/docker-compose.{dev,prod}.yml 全部容器配 json-file driver max-size=100m max-file=3 + tag={{.Name}}
- [ ] **6.5** Redis 容器关闭 AOF（确认数据可丢）
- [ ] **6.6** RDS 自动备份 + 跨区快照 已开启 verify
- [ ] **6.7** Cloudflare 5xx 告警规则
- [ ] **6.8** keystore 三地备份完成（1Password + 离线 GPG U 盘 + Play App Signing 托管）
- [ ] **6.9** RAM 子账号清理 SOP 演练（建一个 → 离职模拟 → 同步禁用）
- [✓] **6.10** scripts/cp_rotate_hmac.py：admin login → regenerate-keys → 输出 dual-accept 操作清单（生产前需扩 schema 加 prev_hmac_secret 列才能真正双接受）
- [✓] **6.11** scripts/locustfile.py：HmacUser 真实签名 /upgrade/check + 多渠道/国家/版本号 random；本地起 backend 即可跑
- [✓] **6.12** 写 `docs/incident-playbook.md`（10 章：DB/CDN/VOD/域名/CF/5xx/安全/红线/凭据/演练）

---

## P7 增长期触发任务（DAU > 10w 才做，**现在不做**）

- [ ] **7.1** 印尼 PSE 注册（Kominfo）
- [ ] **7.2** RDS 升级规格 + 读写分离评估
- [ ] **7.3** LATAM/非洲 流量切到 Cloudflare CDN 评估
- [ ] **7.4** 多 region 部署评估（API 多 region + 数据库主从）
- [ ] **7.5** K8s 迁移评估（ACK 托管版）
- [ ] **7.6** **cp 模块抽离独立 ECS / 独立 RDS schema** 评估（如果接了第二个 App）
