# movie backend

FastAPI + SQLAlchemy + JWT。当前是 MVP 阶段，目的是让 admin-web 能登录走通。

## 当前进度（MVP）

✅ 已完成：
- pyproject + 模块化目录骨架
- SQLAlchemy 2.0 + SQLite（dev）/ MySQL（prod）切换
- JWT access/refresh + bcrypt 密码 + Bearer 鉴权
- `POST /api/v1/admin/auth/login` 登录端点
- `GET /api/v1/admin/auth/me` 当前管理员
- `GET /healthz` `/readyz`
- a_admin_users + a_admin_roles 表
- seed 脚本：4 个 seed 角色 + 1 个超管

⏳ 后续：
- 完整 P3：u_users + OAuth + OTP + refresh token 旋转
- P2：cp_apps 多租户 + Walle 渠道签名
- P4：ct_videos + 地区可见性 + VOD 同步
- 正式 alembic multi-head 迁移（当前用 `create_all`，可重启不丢数据但表结构变更需手动）
- import-linter / 结构化日志 / trace_id / Sentry

## 本地启动

```bash
cd /Users/yikong/Downloads/work/movie/backend

# 1. 复制环境变量
cp .env.example .env

# 2. 安装 Python 3.12 + 依赖（uv 自动管理）
uv sync

# 3. 初始化 SQLite 数据库 + seed 超管
uv run python seed.py

# 4. 启动后端
uv run uvicorn app.main:app --reload --port 8000
```

启动后：
- 健康检查：http://localhost:8000/healthz → `{"status":"ok"}`
- OpenAPI 文档：http://localhost:8000/docs
- 默认超管账号：`admin@movie.local / admin123`（可在 `.env` 改）

## admin-web 联调

```bash
cd /Users/yikong/Downloads/work/movie/admin-web
pnpm install   # 第一次
pnpm dev       # http://localhost:5174/admin/
```
登录页输入 `admin@movie.local / admin123` → 跳转 dashboard placeholder。

vite proxy 自动把 `/api` 转发到 `http://localhost:8000`，无需 CORS 配置；CORS 仍开了以备直接打 IP 调试。

## 数据库切换到 MySQL（生产）

只改 `.env`：
```
DATABASE_URL=mysql+pymysql://user:pass@rds-host.aliyuncs.com:3306/movie_prod
```
首次部署时跑 `uv run python seed.py`（生产仅一次，之后改密）。

## 故障排查

- 端口占用：`lsof -ti:8000 | xargs kill`
- bcrypt 装不上：`uv pip install bcrypt --reinstall`
- 数据库重置：`rm dev.db && uv run python seed.py`
- 看实时日志：`uv run uvicorn app.main:app --reload --log-level debug`
