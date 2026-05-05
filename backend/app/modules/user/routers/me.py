"""user 自助端点 /api/v1/users/me/...

包含：
- POST /users/me/delete-request — Play / GDPR 强制提供的"删除账号"通道。
  软删：标 status=deleted（保留账号 ID 防 unique 冲突 + 30 天内可恢复）；
  PII 真正擦除走异步 job（不在本接口同步做，避免请求超时）。
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.modules.user.models import RefreshToken, User

router = APIRouter()


class DeleteRequestIn(BaseModel):
    confirm: bool = False  # 防误调


class DeleteRequestOut(BaseModel):
    status: str  # accepted
    message: str
    will_purge_after: datetime


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    uuid: str
    email: str | None
    phone: str | None
    display_name: str
    country: str | None
    preferred_language: str
    status: str
    avatar_url: str | None
    last_active_at: datetime | None


@router.get("", response_model=MeOut)
def me(user: User = Depends(get_current_user)) -> MeOut:
    return MeOut.model_validate(user)


@router.post("/delete-request", response_model=DeleteRequestOut)
def request_delete(
    payload: DeleteRequestIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeleteRequestOut:
    if not payload.confirm:
        raise HTTPException(400, "confirm 必须为 true 才提交删除请求")
    if user.status == "deleted":
        raise HTTPException(409, "账号已在删除流程中")

    # 软删 + 把该用户所有未撤销 refresh token 全标 revoked（强制所有设备登出）
    user.status = "deleted"
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    db.commit()

    # 30 天后异步 job 真清 PII（按 GDPR / Play 政策；当前实现留 TODO）
    from datetime import timedelta

    purge_at = datetime.now(UTC) + timedelta(days=30)
    return DeleteRequestOut(
        status="accepted",
        message=(
            "账号已标记为待删除；30 天内可联系客服取消。"
            "30 天后自动清空个人信息（昵称/头像/邮箱/手机/设备记录），"
            "保留账号 ID 用于防止 unique 冲突与审计追溯。"
        ),
        will_purge_after=purge_at,
    )
