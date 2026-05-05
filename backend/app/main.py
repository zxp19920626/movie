from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 让 ORM 类被注册到 Base.metadata（MVP 用 create_all；P1.30 之后切 alembic）
import app.modules.admin.models  # noqa: F401
import app.modules.channel_pack.models  # noqa: F401
import app.modules.content.models  # noqa: F401
import app.modules.user.models  # noqa: F401
from app.api.v1 import api_v1
from app.core.config import settings
from app.core.database import Base, engine
from app.core.logging import configure_logging, get_logger
from app.modules.channel_pack.adapters.object_store import init_default_store
from app.modules.channel_pack.adapters.walle import init_default_signer
from app.shared.media_provider.service import configure_default_providers
from app.shared.middleware.trace_id import TraceIdMiddleware

STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"


configure_logging(level=settings.log_level)
log = get_logger("app.main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    init_default_store(str(STORAGE_DIR), public_url_prefix="/storage")
    init_default_signer(stub=True)
    configure_default_providers()
    log.info("app.startup", storage_dir=str(STORAGE_DIR))
    yield
    log.info("app.shutdown")


app = FastAPI(
    title="movie backend",
    version="0.2.0",
    lifespan=lifespan,
)

# trace_id 必须最先注册（外层），CORS 之后；这样 CORS 的 OPTIONS 也带 trace_id
app.add_middleware(TraceIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    return {"status": "ready"}


# StaticFiles：本地存储映射到 /storage/*；生产换 OSS+CDN（公开端 download_url 自然变）
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")

app.include_router(api_v1)
