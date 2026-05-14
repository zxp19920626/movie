"""A.T2.3 — Walle 签名端到端

覆盖 finalize → fan-out signing jobs → walle 注入 → 上传 → 检查所有 jobs 是否
全 success → 标 version=ready 的完整链路。

策略：
- 用 LocalFSObjectStore 指向 tmp_path（真实文件 IO，验证 put/get/public_url）
- 用 WalleStubSigner（默认即此实现，cp 母包+追加 channel 标记字节）
- monkey-patch `app.modules.channel_pack.tasks.sign_apk.SessionLocal`
  让 BackgroundTasks 入口函数 run_sign_apk_job 也能拿到测试 DB 连接

不修改任何生产代码。
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.modules.channel_pack.adapters import object_store as object_store_mod
from app.modules.channel_pack.adapters import walle as walle_mod
from app.modules.channel_pack.adapters.object_store import (
    LocalFSObjectStore,
    compute_master_key,
    compute_signed_key,
)
from app.modules.channel_pack.adapters.walle import WalleStubSigner
from app.modules.channel_pack.models import (
    CpApkSigningJob,
    CpApp,
    CpAppVersion,
    CpChannel,
)
from app.modules.channel_pack.services.signing_service import (
    check_and_mark_ready,
    compute_idempotency_key,
    fan_out_signing_jobs,
)
from app.modules.channel_pack.tasks import sign_apk as sign_apk_mod
from app.modules.channel_pack.tasks.sign_apk import run_sign_apk_job


@pytest.fixture
def local_store(tmp_path: Path) -> Generator[LocalFSObjectStore, None, None]:
    """每个测试一个独立的 storage 根目录；同时注入到 module 单例里。"""
    store = LocalFSObjectStore(str(tmp_path / "storage"), public_url_prefix="/storage")
    saved = object_store_mod._default_store
    object_store_mod._default_store = store
    yield store
    object_store_mod._default_store = saved


@pytest.fixture
def stub_signer() -> Generator[WalleStubSigner, None, None]:
    """注入 WalleStubSigner（其实默认就是它，显式声明便于测试中替换）。"""
    signer = WalleStubSigner()
    saved = walle_mod._default_signer
    walle_mod._default_signer = signer
    yield signer
    walle_mod._default_signer = saved


@pytest.fixture
def patched_session_local(db: Session) -> Generator[None, None, None]:
    """把 sign_apk 模块里的 SessionLocal 改成绑到测试连接的工厂。

    这样 run_sign_apk_job 内部 db = SessionLocal() 拿到的是同一个测试库视图，
    fan_out 写的 job 它能查到，反过来它写的 status 测试也看得见。
    """
    test_session_local = sessionmaker(
        bind=db.connection(), autoflush=False, autocommit=False
    )
    saved = sign_apk_mod.SessionLocal
    sign_apk_mod.SessionLocal = test_session_local
    yield
    sign_apk_mod.SessionLocal = saved


@pytest.fixture
def seeded(
    db: Session,
    admin_id: int,
    local_store: LocalFSObjectStore,
) -> dict:
    """种 1 个 App + 3 渠道（Play / direct / xiaomi_intl）+ 1 个 draft 版本 + 母包文件。

    finalize 时应该只对 direct + xiaomi_intl 创建 job（Play 跳过）。
    """
    app = CpApp(
        tenant_uuid="tenant-walle-e2e",
        name="WalleE2EApp",
        package_name="com.walle.e2e",
        owner_admin_user_id=admin_id,
        api_key_hash="x",
        hmac_secret="x",
        status="active",
    )
    db.add(app)
    db.flush()

    db.add_all(
        [
            CpChannel(
                app_id=app.id, code="gp", name="Play",
                is_play_store=True, enabled=True, priority=1,
            ),
            CpChannel(
                app_id=app.id, code="direct", name="Direct",
                is_play_store=False, enabled=True, priority=10,
            ),
            CpChannel(
                app_id=app.id, code="xiaomi_intl", name="Xiaomi Intl",
                is_play_store=False, enabled=True, priority=20,
            ),
        ]
    )

    # 把"母包"写到 LocalFS 里（put_stream 会顺便算 sha256/size）
    master_key = compute_master_key(app.tenant_uuid, 100)
    fake_apk_bytes = b"PK\x03\x04" + b"fake-apk-content-bytes" * 10
    import io

    sha, size = local_store.put_stream(master_key, io.BytesIO(fake_apk_bytes))

    version = CpAppVersion(
        app_id=app.id,
        version_code=100,
        version_name="1.0",
        master_apk_oss_key=master_key,
        master_apk_sha256=sha,
        master_apk_size=size,
        status="draft",
        uploaded_by=admin_id,
    )
    db.add(version)
    db.flush()
    db.commit()

    return {"app": app, "version": version, "admin_id": admin_id, "master_sha": sha}


# ===================== T2.3: Walle e2e =====================


def test_finalize_version_fans_out_jobs_for_each_non_play_channel(
    db: Session, seeded: dict
) -> None:
    """3 个 channel（1 Play + 2 非 Play）→ fan_out 创建 2 个 job（Play 跳过）。"""
    jobs = fan_out_signing_jobs(db, seeded["app"], seeded["version"])
    codes = sorted(j.channel_code for j in jobs)
    assert codes == ["direct", "xiaomi_intl"]
    # version 状态推进到 signing
    db.refresh(seeded["version"])
    assert seeded["version"].status == "signing"


def test_signing_job_completes_with_local_fs_and_stub_walle(
    db: Session,
    seeded: dict,
    local_store: LocalFSObjectStore,
    stub_signer: WalleStubSigner,
    patched_session_local: None,
) -> None:
    """完整链路：fan_out → run_sign_apk_job 真跑：
    下母包 → walle stub 注入 channel 标记 → put_file 上传 → DB 写 success。
    """
    jobs = fan_out_signing_jobs(db, seeded["app"], seeded["version"])
    assert len(jobs) == 2

    # 用 run_sign_apk_job 真跑（不走 BackgroundTasks 调度，直接同步触发）
    for job in jobs:
        run_sign_apk_job(job.id)

    # 重新查 jobs（patched SessionLocal 共享连接，所以本会话能看到）
    for job in jobs:
        db.expire(job)
        db.refresh(job)
        assert job.status == "success", (
            f"job {job.channel_code} status={job.status} last_error={job.last_error}"
        )
        # 输出文件真实存在 + 大小 > 母包（stub 末尾追加了 channel 标记）
        assert job.output_oss_key
        assert job.output_oss_key == compute_signed_key(
            seeded["app"].tenant_uuid, 100, job.channel_code
        )
        assert local_store.exists(job.output_oss_key)
        assert job.output_size > seeded["version"].master_apk_size
        assert job.output_sha256 != seeded["version"].master_apk_sha256
        # WalleStub 在末尾追加了 channel 标记 — 验证字节真到了文件
        signed_path = local_store.get_local_path(job.output_oss_key)
        assert signed_path is not None
        with open(signed_path, "rb") as f:
            content = f.read()
        assert f"WALLE_STUB_CHANNEL={job.channel_code}".encode() in content


def test_signing_job_idempotency_key_dedup(
    db: Session, seeded: dict
) -> None:
    """相同 (app_id, version_code, channel, master_sha256) 第二次 finalize 不创建重复 job。"""
    a = fan_out_signing_jobs(db, seeded["app"], seeded["version"])
    b = fan_out_signing_jobs(db, seeded["app"], seeded["version"])
    # 返回同一组 job 实例
    assert {j.id for j in a} == {j.id for j in b}
    # DB 真实记录只有 2 行
    rows = (
        db.query(CpApkSigningJob)
        .filter_by(app_id=seeded["app"].id, version_code=100)
        .all()
    )
    assert len(rows) == 2
    # idempotency_key 也对得上
    expected_keys = {
        compute_idempotency_key(
            seeded["app"].id, 100, ch, seeded["master_sha"]
        )
        for ch in ("direct", "xiaomi_intl")
    }
    assert {r.idempotency_key for r in rows} == expected_keys


def test_all_jobs_success_promotes_version_to_ready(
    db: Session,
    seeded: dict,
    local_store: LocalFSObjectStore,
    stub_signer: WalleStubSigner,
    patched_session_local: None,
) -> None:
    """所有 jobs success → check_and_mark_ready 把 version.status='ready' + released_at 落地。"""
    jobs = fan_out_signing_jobs(db, seeded["app"], seeded["version"])
    for job in jobs:
        run_sign_apk_job(job.id)

    # run_sign_apk_job 内部最后一步会调 check_and_mark_ready，这里也兜底再调一次
    promoted = check_and_mark_ready(db, seeded["app"].id, 100)
    db.expire(seeded["version"])
    db.refresh(seeded["version"])
    # 要么已经在 run_sign_apk_job 里被置成 ready，要么本次显式调用置成 ready
    assert seeded["version"].status == "ready"
    assert seeded["version"].released_at is not None
    # promoted 只看本次调用是否"刚好"完成切换；只要状态终态是 ready 即可
    _ = promoted


def test_signing_job_failure_marks_status(
    db: Session,
    seeded: dict,
    local_store: LocalFSObjectStore,
    patched_session_local: None,
) -> None:
    """walle signer 注入抛错 → job.status='failed' + last_error 落库 + version 不升 ready。"""

    class BrokenSigner:
        def inject_channel(
            self, in_apk_path: str, out_apk_path: str, channel_code: str
        ) -> None:
            raise RuntimeError(f"walle exploded for {channel_code}")

    saved = walle_mod._default_signer
    walle_mod._default_signer = BrokenSigner()
    try:
        jobs = fan_out_signing_jobs(db, seeded["app"], seeded["version"])
        for job in jobs:
            run_sign_apk_job(job.id)
        for job in jobs:
            db.expire(job)
            db.refresh(job)
            assert job.status == "failed"
            assert "walle exploded" in job.last_error
            assert job.output_oss_key == ""  # 没上传
    finally:
        walle_mod._default_signer = saved

    # 版本不应升 ready
    db.expire(seeded["version"])
    db.refresh(seeded["version"])
    assert seeded["version"].status == "signing"  # 仍卡在签名中
