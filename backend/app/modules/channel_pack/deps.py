"""channel_pack FastAPI Depends：app 加载 + 权限校验"""

from fastapi import Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.modules.admin.models import AdminUser
from app.modules.channel_pack.models import CpApp


def get_target_app(
    app_id: int = Path(..., description="cp_apps.id"),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> CpApp:
    app = db.get(CpApp, app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="app not found")
    if not (admin.role and admin.role.is_super_admin):
        if app.tenant_uuid not in (admin.app_scope or []):
            raise HTTPException(status_code=403, detail="无权访问该 App 租户")
    return app


def require_super_admin(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    if not (admin.role and admin.role.is_super_admin):
        raise HTTPException(status_code=403, detail="仅超级管理员可执行此操作")
    return admin
