"""
主应用入口 — FastAPI 应用初始化
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from api.assets import router as assets_router
from api.auth import create_initial_admin, router as auth_router
from api.cases import router as cases_router
from api.chat import router as chat_router
from api.knowledge_db import router as knowledge_db_router
from api.library import router as library_router
from db.models import create_tables
from core.paths import UPLOADS_DIR


_BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(_BACKEND_DIR / ".env")


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    from db.database import SessionLocal

    db = SessionLocal()
    try:
        create_initial_admin(db)
    finally:
        db.close()
    print("谱图智能分析系统已启动，数据库初始化完成")
    yield


def _cors_origins() -> list[str]:
    raw_origins = os.environ.get(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


def _session_secret() -> str:
    secret = os.environ.get("SESSION_SECRET")
    if secret:
        return secret
    if os.environ.get("REQUIRE_SECURE_CONFIG", "false").lower() in {"1", "true", "yes"}:
        raise RuntimeError("生产环境必须设置 SESSION_SECRET")
    return "development-only-change-before-public-deploy"


app = FastAPI(
    title="谱图智能分析系统",
    description="AI 辅助的红外光谱 (FTIR)、DSC、TGA 等谱图数据分析系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=_session_secret(),
    https_only=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"},
    same_site=os.environ.get("SESSION_COOKIE_SAME_SITE", "lax"),
    max_age=60 * 60 * 12,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_UPLOADS_DIR = UPLOADS_DIR
_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(assets_router, prefix="/uploads", tags=["文件"])
app.include_router(chat_router, prefix="/api/v1/chat", tags=["分析"])
app.include_router(library_router, prefix="/api/v1/library", tags=["标准库"])
app.include_router(cases_router, prefix="/api/v1/cases", tags=["案例记录"])
app.include_router(knowledge_db_router, prefix="/api/v1/knowledge", tags=["知识库"])


@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {
        "name": "谱图智能分析系统",
        "version": "1.0.0",
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
