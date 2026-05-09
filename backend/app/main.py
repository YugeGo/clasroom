"""
Campus Room AI Sniper — FastAPI 应用入口
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.browse import router as browse_router
from app.api.chat import router as chat_router
from app.api.query import router as query_router
from app.api.sync import router as sync_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"🚀 {settings.APP_NAME} 启动中...")
    logger.info(f"   教务系统: {settings.EDU_SYSTEM_TYPE} @ {settings.EDU_BASE_URL}")
    logger.info(f"   LLM 模型: {settings.LLM_MODEL}")
    logger.info(f"   验证码方案: {settings.CAPTCHA_SOLVER}")
    yield
    logger.info("应用关闭，清理资源...")


app = FastAPI(
    title=settings.APP_NAME,
    description="空教室 AI 狙击手 - 用 AI 查询高校空教室",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — 允许前端开发服务器访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(browse_router)
app.include_router(chat_router)
app.include_router(query_router)
app.include_router(sync_router)


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
