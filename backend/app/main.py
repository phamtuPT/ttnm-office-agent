import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import tools  # noqa: F401  (đăng ký tool)
from .api import files, sessions, settings as settings_api, ws
from .config import get_settings
from .db import init_db
from .privacy import secrets

logging.basicConfig(level=logging.INFO)
secrets.install()  # che chuỗi giống khoá API trong mọi log


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


settings = get_settings()
app = FastAPI(title="TTNM Office Agent", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
app.include_router(sessions.router)
app.include_router(files.router)
app.include_router(settings_api.router)
app.include_router(ws.router)


@app.get("/api/health")
def health():
    return {"ok": True}
