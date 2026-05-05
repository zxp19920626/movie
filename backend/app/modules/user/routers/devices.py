"""user 模块 — 设备路由 /api/v1/devices/..."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.modules.user.models import User, UserDevice
from app.modules.user.schemas import DeviceOut, DeviceRegisterRequest

router = APIRouter()


@router.post("/register", response_model=DeviceOut)
def register_device(
    payload: DeviceRegisterRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceOut:
    """登记/刷新设备指纹（同 user+device_id+app_id 视为同一设备 → 更新 last_seen）"""
    stmt = select(UserDevice).where(
        UserDevice.user_id == user.id,
        UserDevice.device_id == payload.device_id,
        UserDevice.app_id == payload.app_id,
    )
    dev = db.scalar(stmt)
    now = datetime.now(UTC)
    if dev is None:
        dev = UserDevice(
            user_id=user.id,
            device_id=payload.device_id,
            app_id=payload.app_id,
            platform=payload.platform,
            app_version=payload.app_version,
            channel=payload.channel,
            push_token=payload.push_token,
            country=payload.country,
            last_seen_at=now,
        )
        db.add(dev)
    else:
        dev.platform = payload.platform
        dev.app_version = payload.app_version
        dev.channel = payload.channel
        dev.push_token = payload.push_token
        if payload.country:
            dev.country = payload.country
        dev.last_seen_at = now
    db.commit()
    db.refresh(dev)
    return DeviceOut.model_validate(dev)
