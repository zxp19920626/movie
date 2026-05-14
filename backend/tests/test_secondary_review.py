"""影片二次审核状态机单测：draft → pending → approved/rejected → 重新提审。

被测：
- app.modules.content.routers.admin._REVIEW_TRANSITIONS（状态迁移表本体）
- POST /api/v1/admin/content/videos/{id}/secondary-review（非法路径走的早期校验）

合法迁移（见 _REVIEW_TRANSITIONS）：
  draft     → submit  → pending
  pending   → approve → approved
  pending   → reject  → rejected
  approved  → reject  → rejected   （上架后撤回）
  rejected  → submit  → pending    （重新提审；注意：不是回 draft）

非法路径（任何不在合法集中的迁移）→ 400。

原 production bug — SecondaryReviewOut(model_validate(v)) 缺 video_id 字段（schema 期望
video_id 但 CtVideo 字段叫 id）已在 schemas.py 用 validation_alias='id' 修复。本文件
保留原 DB 状态断言用例 + 增加 response_body 用例验证修复。
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1 import api_v1
from app.core.database import get_db
from app.core.deps import get_current_admin
from app.modules.admin.models import AdminRole, AdminUser
from app.modules.content.models import CtVideo
from app.modules.content.routers.admin import _REVIEW_TRANSITIONS


@pytest.fixture
def admin_user(db: Session) -> AdminUser:
    role = AdminRole(
        code=f"sr_super_{datetime.now(UTC).timestamp()}",
        name="super",
        is_super_admin=True,
        is_builtin=True,
        permissions=[],
    )
    db.add(role)
    db.flush()
    admin = AdminUser(
        email=f"sr_{datetime.now(UTC).timestamp()}@x.com",
        password_hash="x",
        status="active",
        role_id=role.id,
        app_scope=[],
    )
    db.add(admin)
    db.flush()
    db.refresh(admin)
    return admin


@pytest.fixture
def client(db: Session, admin_user: AdminUser) -> TestClient:
    test_app = FastAPI()
    test_app.include_router(api_v1)

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    def _override_get_current_admin() -> AdminUser:
        return admin_user

    test_app.dependency_overrides[get_db] = _override_get_db
    test_app.dependency_overrides[get_current_admin] = _override_get_current_admin
    return TestClient(test_app, raise_server_exceptions=False)


def _new_video(db: Session, *, status: str = "draft") -> CtVideo:
    v = CtVideo(
        code=f"sr-{datetime.now(UTC).timestamp()}-{status}",
        title_i18n={"en": "x"},
        description_i18n={"en": ""},
        type="movie",
        tags=[],
        cast_list=[],
        secondary_review_status=status,
    )
    db.add(v)
    db.flush()
    db.refresh(v)
    return v


# ---------------- 迁移表本体（纯字典断言） ----------------


def test_transition_table_draft_only_submit():
    assert _REVIEW_TRANSITIONS["draft"] == {"submit"}


def test_transition_table_pending_approve_or_reject():
    assert _REVIEW_TRANSITIONS["pending"] == {"approve", "reject"}


def test_transition_table_approved_only_reject():
    """approved 状态唯一合法是 reject（撤回上架）；不允许 approve 或 submit。"""
    assert _REVIEW_TRANSITIONS["approved"] == {"reject"}


def test_transition_table_rejected_only_submit():
    """rejected → submit（重新提审到 pending），不允许直接 approve。"""
    assert _REVIEW_TRANSITIONS["rejected"] == {"submit"}


# ---------------- 合法路径（response body + DB 状态双验证） ----------------


def test_draft_to_pending_via_submit_updates_db(
    db: Session, client: TestClient, admin_user: AdminUser
):
    v = _new_video(db, status="draft")
    db.commit()
    resp = client.post(
        f"/api/v1/admin/content/videos/{v.id}/secondary-review",
        json={"action": "submit", "note": "ready to review"},
    )
    assert resp.status_code == 200, f"response body bug 已修复，应 200 不再 500: {resp.text}"
    body = resp.json()
    assert body["video_id"] == v.id, "response video_id 应等于 CtVideo.id（schema alias 修复）"
    assert body["secondary_review_status"] == "pending"
    db.expire_all()
    after = db.get(CtVideo, v.id)
    assert after is not None
    assert after.secondary_review_status == "pending"
    assert after.secondary_reviewed_by == admin_user.id
    assert after.secondary_review_note == "ready to review"


def test_pending_to_approved_updates_db(db: Session, client: TestClient):
    v = _new_video(db, status="pending")
    db.commit()
    client.post(
        f"/api/v1/admin/content/videos/{v.id}/secondary-review",
        json={"action": "approve"},
    )
    db.expire_all()
    after = db.get(CtVideo, v.id)
    assert after.secondary_review_status == "approved"


def test_pending_to_rejected_updates_db(db: Session, client: TestClient):
    v = _new_video(db, status="pending")
    db.commit()
    client.post(
        f"/api/v1/admin/content/videos/{v.id}/secondary-review",
        json={"action": "reject", "note": "violation"},
    )
    db.expire_all()
    after = db.get(CtVideo, v.id)
    assert after.secondary_review_status == "rejected"
    assert after.secondary_review_note == "violation"


def test_rejected_to_pending_via_resubmit_updates_db(db: Session, client: TestClient):
    """rejected → submit → pending（实现按重新提审路径设计；不回 draft）。"""
    v = _new_video(db, status="rejected")
    db.commit()
    client.post(
        f"/api/v1/admin/content/videos/{v.id}/secondary-review",
        json={"action": "submit"},
    )
    db.expire_all()
    assert db.get(CtVideo, v.id).secondary_review_status == "pending"


def test_approved_can_be_revoked_by_reject_updates_db(db: Session, client: TestClient):
    """approved → reject 合法（撤回上架）。"""
    v = _new_video(db, status="approved")
    db.commit()
    client.post(
        f"/api/v1/admin/content/videos/{v.id}/secondary-review",
        json={"action": "reject", "note": "post-publish takedown"},
    )
    db.expire_all()
    assert db.get(CtVideo, v.id).secondary_review_status == "rejected"


# ---------------- 非法路径（400 早返；不触 schema bug） ----------------


def test_approved_to_pending_directly_rejected(db: Session, client: TestClient):
    """approved 状态发 submit/approve → 非法 → 400 + DB 不变。"""
    v = _new_video(db, status="approved")
    db.commit()
    r = client.post(
        f"/api/v1/admin/content/videos/{v.id}/secondary-review",
        json={"action": "submit"},
    )
    assert r.status_code == 400, r.text
    assert "非法状态流转" in r.json()["detail"]
    # DB 不应被修改
    db.expire_all()
    assert db.get(CtVideo, v.id).secondary_review_status == "approved"


def test_draft_cannot_be_approved_directly(db: Session, client: TestClient):
    v = _new_video(db, status="draft")
    db.commit()
    r = client.post(
        f"/api/v1/admin/content/videos/{v.id}/secondary-review",
        json={"action": "approve"},
    )
    assert r.status_code == 400, r.text
    db.expire_all()
    assert db.get(CtVideo, v.id).secondary_review_status == "draft"


def test_draft_cannot_be_rejected_directly(db: Session, client: TestClient):
    v = _new_video(db, status="draft")
    db.commit()
    r = client.post(
        f"/api/v1/admin/content/videos/{v.id}/secondary-review",
        json={"action": "reject"},
    )
    assert r.status_code == 400, r.text


def test_unknown_action_validation_error(db: Session, client: TestClient):
    """action 不在 {submit, approve, reject} → schema 校验 422。"""
    v = _new_video(db, status="pending")
    db.commit()
    r = client.post(
        f"/api/v1/admin/content/videos/{v.id}/secondary-review",
        json={"action": "delete"},
    )
    assert r.status_code == 422, r.text


def test_video_not_found_404(client: TestClient):
    r = client.post(
        "/api/v1/admin/content/videos/999999999/secondary-review",
        json={"action": "submit"},
    )
    assert r.status_code == 404
