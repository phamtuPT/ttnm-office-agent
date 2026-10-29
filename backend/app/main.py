import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import tools  # noqa: F401  (đăng ký tool)
from .api import files, sessions, ws
from .config import get_settings
from .db import init_db

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


settings = get_settings()
app = FastAPI(title="TTNM Office Agent", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
app.include_router(sessions.router)
app.include_router(files.router)
app.include_router(ws.router)


@app.get("/api/health")
def health():
    return {"ok": True, "llm_provider": settings.llm_provider, "agent_model": settings.agent_model}
