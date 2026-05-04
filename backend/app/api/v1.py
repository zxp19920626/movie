from fastapi import APIRouter

from app.modules.admin.routers import router as admin_auth_router
from app.modules.channel_pack.routers.admin import router as cp_admin_router
from app.modules.channel_pack.routers.app import router as cp_app_router

api_v1 = APIRouter(prefix="/api/v1")

# admin 鉴权
api_v1.include_router(admin_auth_router, prefix="/admin", tags=["admin-auth"])

# App 分发平台 — 公开端
api_v1.include_router(cp_app_router, prefix="/cp", tags=["cp-public"])

# App 分发平台 — 后台
api_v1.include_router(cp_admin_router, prefix="/admin/cp", tags=["cp-admin"])
