"""影片公开可见性单测：地区可见性 + vod_status + secondary_review 联动过滤。

被测：app.modules.content.services
- apply_public_filters：列表 SQL 过滤
- is_video_visible_for：单条命中检查

注意：当前实现是「0 行 region_visibility → 全国家可见（白名单缺失=放开）」，
和 model docstring「缺行视作不可见（默认黑名单制）」不一致；
本测试按**实现实际行为**写，并在用例 doc 标出此 spec/代码分歧（见任务汇报）。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.content.models import CtRegionVisibility, CtVideo
from app.modules.content.services import apply_public_filters, is_video_visible_for


def _new_video(
    db: Session,
    *,
    code: str,
    status: str = "online",
    secondary: str = "approved",
    vod: str = "ready",
) -> CtVideo:
    v = CtVideo(
        code=code,
        title_i18n={"en": code},
        description_i18n={"en": ""},
        type="movie",
        status=status,
        secondary_review_status=secondary,
        vod_status=vod,
        tags=[],
        cast_list=[],
    )
    db.add(v)
    db.flush()
    db.refresh(v)
    return v


@pytest.fixture
def video_visible_all(db: Session) -> CtVideo:
    """完全合规的影片：online + approved + vod=ready + 没有 region 行。"""
    return _new_video(db, code=f"vid-ok-{datetime.now(UTC).timestamp()}")


@pytest.fixture
def video_vod_failed(db: Session) -> CtVideo:
    """vod_status != ready → 列表/详情都看不到。"""
    return _new_video(db, code=f"vid-vodfail-{datetime.now(UTC).timestamp()}", vod="failed")


@pytest.fixture
def video_not_approved(db: Session) -> CtVideo:
    """secondary_review_status != approved → 看不到。"""
    return _new_video(
        db, code=f"vid-pending-{datetime.now(UTC).timestamp()}", secondary="pending"
    )


@pytest.fixture
def video_offline(db: Session) -> CtVideo:
    """status != online → 看不到。"""
    return _new_video(db, code=f"vid-offline-{datetime.now(UTC).timestamp()}", status="offline")


@pytest.fixture
def video_with_region_rows(db: Session) -> CtVideo:
    """有 region_visibility 行：US=visible, JP=hidden。其它国家走「无匹配」路径。"""
    v = _new_video(db, code=f"vid-region-{datetime.now(UTC).timestamp()}")
    db.add(CtRegionVisibility(video_id=v.id, country_code="US", visible=True))
    db.add(CtRegionVisibility(video_id=v.id, country_code="JP", visible=False))
    db.flush()
    return v


# ---------------- apply_public_filters：列表 SQL ----------------


def test_list_excludes_offline(db: Session, video_visible_all: CtVideo, video_offline: CtVideo):
    stmt = apply_public_filters(select(CtVideo), country="US")
    ids = {v.id for v in db.scalars(stmt).all()}
    assert video_visible_all.id in ids
    assert video_offline.id not in ids


def test_list_excludes_not_approved(
    db: Session, video_visible_all: CtVideo, video_not_approved: CtVideo
):
    stmt = apply_public_filters(select(CtVideo), country="US")
    ids = {v.id for v in db.scalars(stmt).all()}
    assert video_visible_all.id in ids
    assert video_not_approved.id not in ids


def test_list_excludes_vod_not_ready(
    db: Session, video_visible_all: CtVideo, video_vod_failed: CtVideo
):
    """vod_status != 'ready' → 列表过滤掉。"""
    stmt = apply_public_filters(select(CtVideo), country="US")
    ids = {v.id for v in db.scalars(stmt).all()}
    assert video_visible_all.id in ids
    assert video_vod_failed.id not in ids


def test_list_region_match_visible(
    db: Session, video_with_region_rows: CtVideo
):
    """有 region 行且某国 visible=true → 该国可见。"""
    stmt = apply_public_filters(select(CtVideo), country="US")
    ids = {v.id for v in db.scalars(stmt).all()}
    assert video_with_region_rows.id in ids


def test_list_region_explicit_hidden(
    db: Session, video_with_region_rows: CtVideo
):
    """有 region 行且某国 visible=false → 该国不可见。"""
    stmt = apply_public_filters(select(CtVideo), country="JP")
    ids = {v.id for v in db.scalars(stmt).all()}
    assert video_with_region_rows.id not in ids


def test_list_region_no_matching_country_hidden(
    db: Session, video_with_region_rows: CtVideo
):
    """有 region 行但没该国一条 → 不可见（白名单制：只有显式 visible=true 才放）。
    边界：US/JP 都没配 → DE 看不到。
    """
    stmt = apply_public_filters(select(CtVideo), country="DE")
    ids = {v.id for v in db.scalars(stmt).all()}
    assert video_with_region_rows.id not in ids


def test_list_country_none_no_region_rows_visible(
    db: Session, video_visible_all: CtVideo
):
    """country=None 且没 region 行 → 可见（早期默认开放）。"""
    stmt = apply_public_filters(select(CtVideo), country=None)
    ids = {v.id for v in db.scalars(stmt).all()}
    assert video_visible_all.id in ids


# ---------------- is_video_visible_for：单条命中 ----------------


def test_single_visible_all_dimensions_ok(db: Session, video_visible_all: CtVideo):
    assert is_video_visible_for(db, video_visible_all, country="US") is True


def test_single_offline_false(db: Session, video_offline: CtVideo):
    assert is_video_visible_for(db, video_offline, country="US") is False


def test_single_vod_not_ready_false(db: Session, video_vod_failed: CtVideo):
    assert is_video_visible_for(db, video_vod_failed, country="US") is False


def test_single_region_rows_country_visible(db: Session, video_with_region_rows: CtVideo):
    assert is_video_visible_for(db, video_with_region_rows, country="US") is True


def test_single_region_rows_country_hidden(db: Session, video_with_region_rows: CtVideo):
    assert is_video_visible_for(db, video_with_region_rows, country="JP") is False


def test_single_region_rows_other_country_hidden(db: Session, video_with_region_rows: CtVideo):
    """配了 region 但没该国 → 视为不可见（默认隐性黑/白名单）。"""
    assert is_video_visible_for(db, video_with_region_rows, country="DE") is False


def test_single_country_lowercase_normalized(
    db: Session, video_with_region_rows: CtVideo
):
    """实现把 country 转成 upper()；小写 'us' 也应能命中。"""
    assert is_video_visible_for(db, video_with_region_rows, country="us") is True
