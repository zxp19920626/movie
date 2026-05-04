"""App 端公开路由：/api/v1/cp/..."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.channel_pack.adapters.object_store import get_default_store
from app.modules.channel_pack.models import CpAppVersion
from app.modules.channel_pack.schemas import UpgradeCheckResponse
from app.modules.channel_pack.services.app_registry import get_app_by_uuid
from app.modules.channel_pack.services.hmac_verifier import (
    verify_signature,
    verify_timestamp,
)
from app.modules.channel_pack.services.upgrade_engine import check_upgrade

router = APIRouter()


def _pick_i18n(d: dict[str, str], country: str, default_locale: str = "en") -> str:
    """简单按国家挑语言：country='ID' → 'id'，country='VN' → 'vi' 之类，找不到回 en"""
    if not d:
        return ""
    country_to_locale = {
        "ID": "id",
        "VN": "vi",
        "PH": "en",
        "TH": "th",
        "BR": "pt",
        "AR": "es",
        "MX": "es",
        "CL": "es",
        "EG": "ar",
        "SA": "ar",
        "AE": "ar",
        "NG": "en",
        "ZA": "en",
    }
    locale = country_to_locale.get((country or "").upper(), default_locale)
    return d.get(locale) or d.get(default_locale) or next(iter(d.values()), "")


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/upgrade/check", response_model=UpgradeCheckResponse)
def upgrade_check(
    request: Request,
    app_id: str = Query(..., description="cp_apps.tenant_uuid"),
    version_code: int = Query(..., gt=0),
    channel: str = Query(..., min_length=1),
    device_id: str = Query(..., min_length=1),
    country: str = Query("", max_length=8),
    ts: int = Query(..., description="unix seconds"),
    sig: str = Query(..., description="HMAC-SHA256 base64"),
    db: Session = Depends(get_db),
) -> UpgradeCheckResponse:
    # 1. 时间戳 5min 内
    if not verify_timestamp(ts):
        raise HTTPException(401, "ts expired")

    # 2. app 存在且 active
    app = get_app_by_uuid(db, app_id)
    if app is None:
        raise HTTPException(401, "app_id invalid")

    # 3. HMAC 校验（canonical = 排序的 query 参数 except sig）
    params = dict(request.query_params)
    if not verify_signature(app.hmac_secret, params, sig):
        raise HTTPException(401, "signature mismatch")

    # 4. 规则引擎
    res = check_upgrade(db, app.id, version_code, channel, country.upper(), device_id)
    if res.match is None:
        return UpgradeCheckResponse(has_update=False)

    rule = res.match.rule
    target = res.match.target_version
    signed = res.match.signed_job

    download_url = get_default_store().public_url(signed.output_oss_key)

    return UpgradeCheckResponse(
        has_update=True,
        target_version_code=target.version_code,
        target_version_name=target.version_name,
        is_force=rule.is_force,
        can_skip=rule.can_skip,
        popup_strategy=rule.popup_strategy,
        popup_interval_hours=rule.popup_interval_hours,
        popup_title=_pick_i18n(rule.popup_title_i18n, country),
        popup_content=_pick_i18n(rule.popup_content_i18n, country),
        confirm_text=_pick_i18n(rule.confirm_text_i18n, country),
        cancel_text=_pick_i18n(rule.cancel_text_i18n, country),
        download_url=download_url,
        sha256=signed.output_sha256,
        size=signed.output_size,
    )


# 静默引用，避免 unused
_ = CpAppVersion
