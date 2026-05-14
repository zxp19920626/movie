"""App 端公开路由：/api/v1/cp/..."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.channel_pack.adapters.object_store import get_default_store
from app.modules.channel_pack.models import CpApkSigningJob, CpAppVersion
from app.modules.channel_pack.schemas import PopupButtonResolved, UpgradeCheckResponse
from app.modules.channel_pack.services.app_registry import get_app_by_uuid
from app.modules.channel_pack.services.hmac_verifier import (
    verify_signature,
    verify_timestamp,
)
from app.modules.channel_pack.services.i18n_fallback import choose_locale, pick_i18n
from app.modules.channel_pack.services.popup_button_resolver import resolve_popup_buttons
from app.modules.channel_pack.services.upgrade_engine import check_upgrade

router = APIRouter()


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

    accept_language = request.headers.get("Accept-Language")
    locales = choose_locale(country, accept_language)
    resolved_buttons = resolve_popup_buttons(rule.popup_buttons or [], locales)

    return UpgradeCheckResponse(
        has_update=True,
        target_version_code=target.version_code,
        target_version_name=target.version_name,
        is_force=rule.is_force,
        can_skip=rule.can_skip,
        popup_strategy=rule.popup_strategy,
        popup_interval_hours=rule.popup_interval_hours,
        popup_title=pick_i18n(rule.popup_title_i18n, locales) or "",
        popup_content=pick_i18n(rule.popup_content_i18n, locales) or "",
        confirm_text=pick_i18n(rule.confirm_text_i18n, locales) or "",
        cancel_text=pick_i18n(rule.cancel_text_i18n, locales) or "",
        download_url=download_url,
        sha256=signed.output_sha256,
        size=signed.output_size,
        popup_buttons=[PopupButtonResolved(**b) for b in resolved_buttons],
    )


@router.get("/apk/{tenant_uuid}/{channel_code}/{version_code}", status_code=302)
def apk_redirect(
    request: Request,
    tenant_uuid: str = Path(..., min_length=8),
    channel_code: str = Path(..., min_length=1, max_length=64),
    version_code: int = Path(..., gt=0),
    ts: int = Query(..., description="unix seconds"),
    sig: str = Query(..., description="HMAC-SHA256 base64"),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """便利端点：302 跳到该渠道签好的 APK 真实下载地址（dev 走 /storage；
    生产换 OSS+CDN 时改 object_store.public_url 一处即可）。

    URL 包含 HMAC 防盗链 + ts 防 replay；与 /upgrade/check 同密钥。
    """
    if not verify_timestamp(ts):
        raise HTTPException(401, "ts expired")
    app = get_app_by_uuid(db, tenant_uuid)
    if app is None:
        raise HTTPException(401, "app not found")

    # 用与 /upgrade/check 相同的 canonical 算法验签（参数排序）
    params = {
        "tenant_uuid": tenant_uuid,
        "channel_code": channel_code,
        "version_code": str(version_code),
        "ts": str(ts),
    }
    # 也允许 query 里有更多参数（防御未来增项）
    for k, v in request.query_params.items():
        params.setdefault(k, v)
    if not verify_signature(app.hmac_secret, params, sig):
        raise HTTPException(401, "signature mismatch")

    job = db.scalars(
        select(CpApkSigningJob).where(
            CpApkSigningJob.app_id == app.id,
            CpApkSigningJob.version_code == version_code,
            CpApkSigningJob.channel_code == channel_code,
            CpApkSigningJob.status == "success",
        )
    ).one_or_none()
    if job is None:
        raise HTTPException(404, "signed apk not found")

    url = get_default_store().public_url(job.output_oss_key)
    return RedirectResponse(url=url, status_code=302)


# 静默引用，避免 unused
_ = CpAppVersion
