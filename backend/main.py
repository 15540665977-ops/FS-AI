"""
主应用入口 — FastAPI 应用初始化
# reload-trigger
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.models import create_tables
from api.chat import router as chat_router
from api.library import router as library_router
from api.cases import router as cases_router

app = FastAPI(
    title="谱图智能分析系统",
    description="AI 辅助的红外光谱 (FTIR)、DSC、TGA 等谱图数据分析系统",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api/v1/chat", tags=["分析"])
app.include_router(library_router, prefix="/api/v1/library", tags=["标准库"])
app.include_router(cases_router, prefix="/api/v1/cases", tags=["案例记录"])


@app.on_event("startup")
async def startup_event():
    create_tables()
    print("谱图智能分析系统已启动，数据库初始化完成")


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
