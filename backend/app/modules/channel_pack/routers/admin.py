"""admin 端路由：/api/v1/admin/cp/..."""

import base64
import secrets
import uuid
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.core.security import hash_password
from app.modules.admin.models import AdminUser
from app.modules.channel_pack.adapters.object_store import (
    compute_master_key,
    file_sha256,
    get_default_store,
)
from app.modules.channel_pack.deps import get_target_app, require_super_admin
from app.modules.channel_pack.models import (
    CpApkSigningJob,
    CpApp,
    CpAppVersion,
    CpChannel,
    CpUpgradeRule,
)
from app.modules.channel_pack.schemas import (
    AppCreate,
    AppCreateResponse,
    AppList,
    AppOut,
    AppRegenerateResponse,
    AppUpdate,
    ChannelCreate,
    ChannelList,
    ChannelOut,
    ChannelUpdate,
    PopupButton,
    RuleCreate,
    RuleList,
    RuleOut,
    RulePreviewRequest,
    RulePreviewResponse,
    RuleUpdate,
    SigningJobList,
    SigningJobOut,
    VersionList,
    VersionOut,
)
from app.modules.channel_pack.services.app_registry import invalidate
from app.modules.channel_pack.services.signing_service import fan_out_signing_jobs
from app.modules.channel_pack.services.upgrade_engine import check_upgrade
from app.modules.channel_pack.services.upgrade_rule_validator import (
    UpgradeRuleValidationError,
    validate_buttons_for_app,
)
from app.modules.channel_pack.tasks.sign_apk import run_sign_apk_job

router = APIRouter()


def _new_api_key() -> str:
    return "cpk_" + secrets.token_urlsafe(32)


def _new_hmac_secret() -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode()


# ============== Apps（多租户根） ==============


@router.get("/apps", response_model=AppList)
def list_apps(
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> AppList:
    stmt = select(CpApp)
    if not (admin.role and admin.role.is_super_admin):
        scope = admin.app_scope or []
        if not scope:
            return AppList(items=[], total=0)
        stmt = stmt.where(CpApp.tenant_uuid.in_(scope))
    total = len(list(db.scalars(stmt).all()))
    items = list(db.scalars(stmt.order_by(CpApp.id.desc()).limit(limit).offset(offset)).all())
    return AppList(items=[AppOut.model_validate(a) for a in items], total=total)


@router.post("/apps", response_model=AppCreateResponse, status_code=201)
def create_app(
    payload: AppCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_super_admin),
) -> AppCreateResponse:
    api_key = _new_api_key()
    hmac_secret = _new_hmac_secret()
    app = CpApp(
        tenant_uuid=str(uuid.uuid4()),
        name=payload.name,
        package_name=payload.package_name,
        owner_admin_user_id=payload.owner_admin_user_id or admin.id,
        api_key_hash=hash_password(api_key),
        hmac_secret=hmac_secret,
        status="active",
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return AppCreateResponse(
        app=AppOut.model_validate(app), api_key=api_key, hmac_secret=hmac_secret
    )


@router.get("/apps/{app_id}", response_model=AppOut)
def get_app(app: CpApp = Depends(get_target_app)) -> AppOut:
    return AppOut.model_validate(app)


@router.patch("/apps/{app_id}", response_model=AppOut)
def update_app(
    payload: AppUpdate,
    app: CpApp = Depends(get_target_app),
    db: Session = Depends(get_db),
) -> AppOut:
    if payload.name is not None:
        app.name = payload.name
    if payload.package_name is not None:
        app.package_name = payload.package_name
    if payload.status is not None:
        app.status = payload.status
    db.commit()
    invalidate(app.tenant_uuid)
    return AppOut.model_validate(app)


@router.delete("/apps/{app_id}", status_code=204)
def delete_app(
    app: CpApp = Depends(get_target_app),
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_super_admin),
) -> None:
    invalidate(app.tenant_uuid)
    db.delete(app)
    db.commit()


@router.post("/apps/{app_id}/regenerate-keys", response_model=AppRegenerateResponse)
def regenerate_keys(
    app: CpApp = Depends(get_target_app),
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_super_admin),
) -> AppRegenerateResponse:
    api_key = _new_api_key()
    hmac_secret = _new_hmac_secret()
    app.api_key_hash = hash_password(api_key)
    app.hmac_secret = hmac_secret
    db.commit()
    invalidate(app.tenant_uuid)
    return AppRegenerateResponse(api_key=api_key, hmac_secret=hmac_secret)


# ============== Channels ==============


@router.get("/apps/{app_id}/channels", response_model=ChannelList)
def list_channels(
    app: CpApp = Depends(get_target_app), db: Session = Depends(get_db)
) -> ChannelList:
    items = list(
        db.scalars(
            select(CpChannel).where(CpChannel.app_id == app.id).order_by(CpChannel.priority.asc())
        ).all()
    )
    return ChannelList(items=[ChannelOut.model_validate(c) for c in items], total=len(items))


@router.post("/apps/{app_id}/channels", response_model=ChannelOut, status_code=201)
def create_channel(
    payload: ChannelCreate,
    app: CpApp = Depends(get_target_app),
    db: Session = Depends(get_db),
) -> ChannelOut:
    existing = db.scalars(
        select(CpChannel).where(CpChannel.app_id == app.id, CpChannel.code == payload.code)
    ).one_or_none()
    if existing:
        raise HTTPException(409, f"channel code '{payload.code}' 已存在")
    channel = CpChannel(
        app_id=app.id,
        code=payload.code,
        name=payload.name,
        is_play_store=payload.is_play_store,
        signing_strategy=payload.signing_strategy,
        enabled=payload.enabled,
        priority=payload.priority,
        oss_prefix=f"apks/{app.tenant_uuid}/",
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return ChannelOut.model_validate(channel)


@router.patch("/apps/{app_id}/channels/{channel_id}", response_model=ChannelOut)
def update_channel(
    payload: ChannelUpdate,
    channel_id: int = Path(...),
    app: CpApp = Depends(get_target_app),
    db: Session = Depends(get_db),
) -> ChannelOut:
    channel = db.get(CpChannel, channel_id)
    if channel is None or channel.app_id != app.id:
        raise HTTPException(404, "channel not found")
    for f in ("name", "is_play_store", "signing_strategy", "enabled", "priority"):
        v = getattr(payload, f)
        if v is not None:
            setattr(channel, f, v)
    db.commit()
    return ChannelOut.model_validate(channel)


@router.delete("/apps/{app_id}/channels/{channel_id}", status_code=204)
def delete_channel(
    channel_id: int = Path(...),
    app: CpApp = Depends(get_target_app),
    db: Session = Depends(get_db),
) -> None:
    channel = db.get(CpChannel, channel_id)
    if channel is None or channel.app_id != app.id:
        raise HTTPException(404, "channel not found")
    db.delete(channel)
    db.commit()


# ============== Versions ==============


@router.get("/apps/{app_id}/versions", response_model=VersionList)
def list_versions(
    app: CpApp = Depends(get_target_app), db: Session = Depends(get_db)
) -> VersionList:
    items = list(
        db.scalars(
            select(CpAppVersion)
            .where(CpAppVersion.app_id == app.id)
            .order_by(CpAppVersion.version_code.desc())
        ).all()
    )
    return VersionList(items=[VersionOut.model_validate(v) for v in items], total=len(items))


@router.post("/apps/{app_id}/versions", response_model=VersionOut, status_code=201)
def upload_version(
    apk_file: UploadFile = File(...),
    version_code: int = Form(...),
    version_name: str = Form(...),
    min_supported_version_code: int = Form(0),
    changelog_i18n: str = Form("{}"),  # JSON 字符串
    app: CpApp = Depends(get_target_app),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> VersionOut:
    import json

    if version_code <= 0:
        raise HTTPException(400, "version_code 必须 > 0")

    # 严格递增校验
    max_existing = db.scalar(
        select(CpAppVersion.version_code)
        .where(CpAppVersion.app_id == app.id)
        .order_by(CpAppVersion.version_code.desc())
        .limit(1)
    )
    if max_existing is not None and version_code <= max_existing:
        raise HTTPException(
            400, f"version_code 必须严格大于历史最大值 {max_existing}（防止灰度回滚踩坑）"
        )

    try:
        cl = json.loads(changelog_i18n) if changelog_i18n else {}
    except json.JSONDecodeError as e:
        raise HTTPException(400, "changelog_i18n 不是合法 JSON") from e

    # 写文件到 object store
    store = get_default_store()
    master_key = compute_master_key(app.tenant_uuid, version_code)
    if apk_file.file is None:
        raise HTTPException(400, "apk_file 缺失")
    sha, size = store.put_stream(master_key, apk_file.file)

    version = CpAppVersion(
        app_id=app.id,
        version_code=version_code,
        version_name=version_name,
        master_apk_oss_key=master_key,
        master_apk_sha256=sha,
        master_apk_size=size,
        min_supported_version_code=min_supported_version_code,
        changelog_i18n=cl,
        status="draft",
        uploaded_by=admin.id,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return VersionOut.model_validate(version)


@router.delete("/apps/{app_id}/versions/{version_id}", status_code=204)
def delete_version(
    version_id: int = Path(...),
    app: CpApp = Depends(get_target_app),
    db: Session = Depends(get_db),
) -> None:
    version = db.get(CpAppVersion, version_id)
    if version is None or version.app_id != app.id:
        raise HTTPException(404, "version not found")
    if version.status == "ready":
        raise HTTPException(400, "已发布版本不能删除（archive 后再删）")
    # 删除文件 + DB 行
    get_default_store().delete(version.master_apk_oss_key)
    db.delete(version)
    db.commit()


@router.post("/apps/{app_id}/versions/{version_id}/finalize", response_model=VersionOut)
def finalize_version(
    background_tasks: BackgroundTasks,
    version_id: int = Path(...),
    app: CpApp = Depends(get_target_app),
    db: Session = Depends(get_db),
) -> VersionOut:
    version = db.get(CpAppVersion, version_id)
    if version is None or version.app_id != app.id:
        raise HTTPException(404, "version not found")
    if version.status not in ("draft", "signing"):
        raise HTTPException(400, f"version status={version.status} 不能 finalize")

    jobs = fan_out_signing_jobs(db, app, version)
    # 把 pending/failed 的 job 调度起来
    for job in jobs:
        if job.status in ("pending", "failed"):
            background_tasks.add_task(run_sign_apk_job, job.id)
    db.refresh(version)
    return VersionOut.model_validate(version)


# ============== Rules ==============


@router.get("/apps/{app_id}/rules", response_model=RuleList)
def list_rules(app: CpApp = Depends(get_target_app), db: Session = Depends(get_db)) -> RuleList:
    items = list(
        db.scalars(
            select(CpUpgradeRule)
            .where(CpUpgradeRule.app_id == app.id)
            .order_by(CpUpgradeRule.priority.desc(), CpUpgradeRule.id.desc())
        ).all()
    )
    return RuleList(items=[RuleOut.model_validate(r) for r in items], total=len(items))


def _effective_play_channel_for_rule(
    db: Session, app: CpApp, channel_codes: list[str]
) -> CpChannel | None:
    """规则触达 Play Store 渠道时返回该渠道；用于按钮 inapp_apk 校验（C2 红线）。

    - channel_codes 非空 → 规则仅对这些渠道生效，按 deps 的 rule 级校验已经拒了 Play，这里返 None
    - channel_codes 为空（apply-to-all） → 若 app 有任何 enabled Play 渠道则需触发 Play 限制
    """
    if channel_codes:
        return None
    return db.scalar(
        select(CpChannel)
        .where(
            CpChannel.app_id == app.id,
            CpChannel.is_play_store.is_(True),
            CpChannel.enabled.is_(True),
        )
        .limit(1)
    )


@router.post("/apps/{app_id}/rules", response_model=RuleOut, status_code=201)
def create_rule(
    payload: RuleCreate,
    app: CpApp = Depends(get_target_app),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> RuleOut:
    if payload.version_code_min > payload.version_code_max:
        raise HTTPException(400, "version_code_min > version_code_max")
    if payload.device_id_hash_mod_min > payload.device_id_hash_mod_max:
        raise HTTPException(400, "device_id_hash_mod 区间非法")
    # 校验 channel_codes 不含 is_play_store
    if payload.channel_codes:
        play_codes = list(
            db.scalars(
                select(CpChannel.code).where(
                    CpChannel.app_id == app.id,
                    CpChannel.code.in_(payload.channel_codes),
                    CpChannel.is_play_store.is_(True),
                )
            ).all()
        )
        if play_codes:
            raise HTTPException(400, f"channel_codes 不能包含 Play Store 渠道：{play_codes}")

    effective_play_channel = _effective_play_channel_for_rule(db, app, payload.channel_codes)
    try:
        validate_buttons_for_app(app, effective_play_channel, payload.popup_buttons)
    except UpgradeRuleValidationError as e:
        raise HTTPException(422, str(e)) from e

    rule = CpUpgradeRule(app_id=app.id, created_by=admin.id, **payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return RuleOut.model_validate(rule)


@router.patch("/apps/{app_id}/rules/{rule_id}", response_model=RuleOut)
def update_rule(
    payload: RuleUpdate,
    rule_id: int = Path(...),
    app: CpApp = Depends(get_target_app),
    db: Session = Depends(get_db),
) -> RuleOut:
    rule = db.get(CpUpgradeRule, rule_id)
    if rule is None or rule.app_id != app.id:
        raise HTTPException(404, "rule not found")

    updates = payload.model_dump(exclude_unset=True)

    # 组装最终态用于校验（payload 没传的字段用 rule 现值）
    final_channel_codes = (
        updates["channel_codes"] if "channel_codes" in updates else (rule.channel_codes or [])
    )
    if "popup_buttons" in updates:
        final_buttons_raw = updates["popup_buttons"] or []
    else:
        final_buttons_raw = rule.popup_buttons or []
    final_buttons = [
        b if isinstance(b, PopupButton) else PopupButton.model_validate(b)
        for b in final_buttons_raw
    ]

    effective_play_channel = _effective_play_channel_for_rule(db, app, final_channel_codes)
    try:
        validate_buttons_for_app(app, effective_play_channel, final_buttons)
    except UpgradeRuleValidationError as e:
        raise HTTPException(422, str(e)) from e

    for k, v in updates.items():
        setattr(rule, k, v)
    db.commit()
    return RuleOut.model_validate(rule)


@router.delete("/apps/{app_id}/rules/{rule_id}", status_code=204)
def delete_rule(
    rule_id: int = Path(...),
    app: CpApp = Depends(get_target_app),
    db: Session = Depends(get_db),
) -> None:
    rule = db.get(CpUpgradeRule, rule_id)
    if rule is None or rule.app_id != app.id:
        raise HTTPException(404, "rule not found")
    db.delete(rule)
    db.commit()


@router.post("/apps/{app_id}/rules/preview", response_model=RulePreviewResponse)
def preview_rule(
    payload: RulePreviewRequest,
    app: CpApp = Depends(get_target_app),
    db: Session = Depends(get_db),
) -> RulePreviewResponse:
    res = check_upgrade(
        db, app.id, payload.version_code, payload.channel, payload.country, payload.device_id
    )
    if res.match is None:
        return RulePreviewResponse(has_update=False, debug_steps=res.debug_steps)
    return RulePreviewResponse(
        has_update=True,
        matched_rule_id=res.match.rule.id,
        matched_rule_name=res.match.rule.name,
        target_version_code=res.match.target_version.version_code,
        is_force=res.match.rule.is_force,
        debug_steps=res.debug_steps,
    )


# ============== Signing Jobs ==============


@router.get("/apps/{app_id}/signing-jobs", response_model=SigningJobList)
def list_signing_jobs(
    app: CpApp = Depends(get_target_app),
    db: Session = Depends(get_db),
    version_code: int | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
) -> SigningJobList:
    stmt = select(CpApkSigningJob).where(CpApkSigningJob.app_id == app.id)
    if version_code is not None:
        stmt = stmt.where(CpApkSigningJob.version_code == version_code)
    if status_filter:
        stmt = stmt.where(CpApkSigningJob.status == status_filter)
    items = list(db.scalars(stmt.order_by(CpApkSigningJob.id.desc())).all())
    return SigningJobList(items=[SigningJobOut.model_validate(j) for j in items], total=len(items))


@router.post("/apps/{app_id}/signing-jobs/{job_id}/retry", response_model=SigningJobOut)
def retry_signing_job(
    background_tasks: BackgroundTasks,
    job_id: int = Path(...),
    app: CpApp = Depends(get_target_app),
    db: Session = Depends(get_db),
) -> SigningJobOut:
    job = db.get(CpApkSigningJob, job_id)
    if job is None or job.app_id != app.id:
        raise HTTPException(404, "job not found")
    if job.status == "running":
        raise HTTPException(400, "job is running")
    if job.status == "success":
        raise HTTPException(400, "job already success")
    # 重置为 pending，让 worker 接管
    job.status = "pending"
    job.last_error = ""
    job.finished_at = None
    db.commit()
    background_tasks.add_task(run_sign_apk_job, job.id)
    return SigningJobOut.model_validate(job)


# 让 unused import 不爆 ruff
_ = (datetime, UTC, file_sha256, status)
