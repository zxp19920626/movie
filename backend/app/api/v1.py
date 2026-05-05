from fastapi import APIRouter

from app.modules.admin.rbac_routers import router as admin_rbac_router
from app.modules.admin.routers import router as admin_auth_router
from app.modules.channel_pack.routers.admin import router as cp_admin_router
from app.modules.channel_pack.routers.app import router as cp_app_router
from app.modules.content.routers.admin import router as content_admin_router
from app.modules.content.routers.app import router as content_app_router
from app.modules.content.routers.watch_history import router as watch_history_router
from app.modules.user.routers.admin import router as user_admin_router
from app.modules.user.routers.auth import router as user_auth_router
from app.modules.user.routers.devices import router as user_devices_router
from app.modules.user.routers.me import router as user_me_router

api_v1 = APIRouter(prefix="/api/v1")

# admin 鉴权
api_v1.include_router(admin_auth_router, prefix="/admin", tags=["admin-auth"])

# C 端用户认证
api_v1.include_router(user_auth_router, prefix="/auth", tags=["user-auth"])
api_v1.include_router(user_devices_router, prefix="/devices", tags=["user-devices"])

# App 分发平台 — 公开端
api_v1.include_router(cp_app_router, prefix="/cp", tags=["cp-public"])

# App 分发平台 — 后台
api_v1.include_router(cp_admin_router, prefix="/admin/cp", tags=["cp-admin"])

# 用户资源 — 后台
api_v1.include_router(user_admin_router, prefix="/admin", tags=["admin-users"])

# 影片资源 — 后台
api_v1.include_router(content_admin_router, prefix="/admin/content", tags=["content-admin"])

# 影片 — App 端
api_v1.include_router(content_app_router, prefix="/videos", tags=["content-public"])

# 观看历史 — App 端
api_v1.include_router(watch_history_router, prefix="/watch-history", tags=["watch-history"])

# 用户自助 — App 端
api_v1.include_router(user_me_router, prefix="/users/me", tags=["user-me"])

# RBAC — 角色 / 管理员 / 权限树（P3.14c）
api_v1.include_router(admin_rbac_router, prefix="/admin/rbac", tags=["admin-rbac"])
