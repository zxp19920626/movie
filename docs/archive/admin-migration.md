# admin-web 由 nextstream 搬迁的资产清单

> 本文档记录 movie 的 `admin-web/` 是如何从 `/Users/yikong/Downloads/nextstream/admin/` 搬迁过来的，便于后续审计与可能的反向同步。

## 一、文件级映射

| nextstream 源文件 | movie 目标文件 | 状态 | 改动说明 |
|---|---|---|---|
| `package.json` | `admin-web/package.json` | 改写 | 项目名 → movie-admin；新增 axios + dayjs；移除项目特定依赖 |
| `vite.config.ts` | `admin-web/vite.config.ts` | 微改 | proxy 端口 8080 → 8000（FastAPI 默认） |
| `tsconfig.json` / `tsconfig.app.json` / `tsconfig.node.json` | 同名 | 完全复制 | 无改动 |
| `index.html` | `admin-web/index.html` | 改写 | title 改为"Movie 管理后台" |
| `.gitignore` | 同名 | 完全复制 | |
| `src/main.ts` | `admin-web/src/main.ts` | 完全复制 | |
| `src/App.vue` | `admin-web/src/App.vue` | 完全复制 | |
| `src/styles/main.css` | `admin-web/src/styles/main.css` | 改写 | CSS 变量 ns- → mv-；主色橙色 → 蓝色（Movie 品牌） |
| `src/api/client.ts` | `admin-web/src/shared/api/client.ts` | 改写 | BASE 路径 `/api` → `/api/v1`；token key 改 mv_admin_*；error 字段适配 FastAPI 的 `detail` |
| `src/stores/auth.ts` | `admin-web/src/shared/stores/auth.ts` | 重写 | 适配多租户：增加 app_scope / current_app_id / hasPermission / canSeeApp；登录 endpoint 改为 `/api/v1/admin/auth/login`；返回字段 `access_token` + `refresh_token`（FastAPI 风格） |
| `src/views/LoginView.vue` | `admin-web/src/shared/layout/LoginView.vue` | 改写 | 品牌文案；去演示账号；不再硬编码 ADMIN role 校验（交给后端） |
| `src/views/LayoutView.vue` | `admin-web/src/shared/layout/LayoutView.vue` | 重写 | 导航重组（按模块 cp/content/user/admin 而非 nextstream 的功能划分）；菜单按 hasPermission 过滤；显示当前租户 |
| `src/router/index.ts` | `admin-web/src/router/index.ts` | 重写 | 按模块拆 17 条路由（P2/P3/P4 实现时替换 placeholder）；增加权限路由守卫 |

## 二、丢弃的文件（仅作设计参考）

以下文件**未搬迁**，但保留在 `nextstream/` 原位，作为实现 P2/P3/P4 时的设计参考：

| nextstream 文件 | 何时参考 | 备注 |
|---|---|---|
| `src/views/ChannelView.vue` | P2.35 渠道管理页 | 单租户设计，需补 app_id 选择器 |
| `src/stores/channel.ts` (304 行) | P2.35-2.38 | 推荐弹窗策略 enum 已采纳到 PROMPT.md |
| `src/views/ListingView.vue` | P2.37 升级规则 | AB 面机制 v1 不做（保留作为 backlog） |
| `src/stores/listing.ts` (207 行) | P2.37 | 区域规则可借鉴，hash bucket 灰度优先 |
| `src/views/ContentView.vue` (21KB) | P4.19 影片管理页 | 字段命名已采纳到 ct_videos |
| `src/views/MembershipView.vue` | P3 用户管理页 | 会员业务不做（v1 无付费）；用户列表/搜索可参考 |
| `src/views/PermissionsView.vue` (178 行) | P3.14c 权限管理页 | 6 模块 × view/edit + 4 seed 角色 已采纳 |
| `src/stores/permission.ts` (228 行) | P3.14a-d | RBAC 权限树设计已采纳 |
| `src/views/DashboardView.vue` | P5+.18 仪表盘 | KPI + ECharts 已采纳 |
| `src/api/admin.ts` | 各模块 api/ | TypeScript 类型设计可参考；端点路径要全部改 |
| `src/components/{channel,listing,permission}/` | 对应模块 components/ | 子组件视情况搬 |

## 三、搬迁后的差异点（部署/运行）

| 项 | nextstream | movie | 影响 |
|---|---|---|---|
| 后端 | Express:8080 | FastAPI:8000 | vite proxy 已改 |
| 后端 API | `/api/...` | `/api/v1/...` | client.ts BASE 已改 |
| 认证响应 | `{token, user}` | `{access_token, refresh_token, user}` | auth.ts 已改 |
| User.role | 字符串 'USER'/'ADMIN' | RBAC（is_super_admin + role + permissions[]） | auth.ts 已改 |
| 多租户 | 无 | 有（current_app_id） | auth.ts 已加 |
| 数据库 | SQLite/Prisma | MySQL/SQLAlchemy | 完全独立，无影响前端 |

## 四、未来反向同步

如果 nextstream 后续有改进想拉回 movie：
- **可拉**：构建配置、布局视觉风格、子组件实现
- **不要拉**：业务 stores（多租户/单租户差太多）、API 类型（端点路径不同）、router（结构不同）
