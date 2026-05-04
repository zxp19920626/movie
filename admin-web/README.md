# movie-admin

Movie 项目管理后台。Vue3 + Vite + TS + Element Plus + Pinia。

## 来源说明

骨架基于 [nextstream](https://github.com/...) 的 admin 目录搬迁并重组：
- 保留：构建配置、Layout 壳子、Login 壳子、Pinia/Element 集成
- 改写：API 客户端（→ FastAPI）、auth store（→ 多租户 + RBAC）、目录（→ 按模块）、品牌（→ Movie 蓝主题）
- 删除：业务 stores（channel/listing/permission）、所有业务 views — 这些是 P2/P3/P4 任务

## 目录结构

```
admin-web/
├── src/
│   ├── shared/            跨模块共用
│   │   ├── api/           axios/fetch 客户端
│   │   ├── stores/        全局 store（auth）
│   │   ├── layout/        LayoutView, LoginView
│   │   └── components/
│   ├── modules/           按业务模块（与 backend 对齐）
│   │   ├── channel-pack/  App 分发平台（P2）
│   │   ├── content/       影视内容（P4）
│   │   ├── user/          用户管理（P3）
│   │   └── admin/         管理员/RBAC（P3）
│   ├── router/            路由聚合
│   ├── styles/
│   ├── main.ts
│   └── App.vue
├── package.json
└── vite.config.ts
```

## 运行

```bash
pnpm install
pnpm dev          # http://localhost:5174/admin/
pnpm build        # 产物 dist/，由 nginx 托管
```

dev 时 vite proxy 会把 `/api` 转发到 `http://localhost:8000`（FastAPI）。

## 后端依赖

需要 backend 提供 `/api/v1/admin/auth/login` 端点，返回：
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "user": {
    "id": "...",
    "email": "...",
    "display_name": "...",
    "role": "super_admin",
    "app_scope": ["tenant_uuid_1", "tenant_uuid_2"],
    "permissions": ["cp.view", "cp.edit", "content.view", ...],
    "is_super_admin": true
  }
}
```

## 设计参考

`nextstream/admin/src/{views,stores,components}/` 是好的设计参考来源。
但**不要直接复制业务代码**——movie 是多租户 + HMAC + FastAPI，与 nextstream 单租户 + Express 设计不同。
