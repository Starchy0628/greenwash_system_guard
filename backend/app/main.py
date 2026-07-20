"""谛观 GreenwashGuard — FastAPI 主入口"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
sys.path.insert(0, str(BASE_DIR.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import get_settings
from app.core.database import init_db, engine
from app.core.logging_setup import setup_logging, RequestLoggingMiddleware, get_logger
from app.api.dashboard import router as dashboard_router
from app.api.companies import router as companies_router
from app.api.analysis import router as analysis_router
from app.api.stream_analysis import router as stream_router
from app.api.watchlist import router as watchlist_router

from app.api.pdf_analysis import router as pdf_router

settings = get_settings()

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库和日志"""
    setup_logging(
        log_level=settings.log_level,
        log_dir=str(BASE_DIR.parent / "logs") if settings.debug else None,
        json_format=False,
    )
    logger.info("正在初始化数据库...")
    init_db()
    logger.info("系统启动完成")
    yield
    logger.info("系统关闭中...")


app = FastAPI(
    title="谛观 GreenwashGuard",
    description="基于异构大语言模型集成推理的企业漂绿风险监测系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard_router)
app.include_router(companies_router)
app.include_router(analysis_router)
app.include_router(stream_router)
app.include_router(watchlist_router)

app.include_router(pdf_router)


# 挂载前端静态文件（如果存在）
if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    
    @app.get("/favicon.svg")
    async def favicon():
        fav = FRONTEND_DIST / "favicon.svg"
        if fav.exists():
            return FileResponse(str(fav))
        return {"message": "ok"}
    
    @app.get("/favicon.ico")
    async def favicon_ico():
        fav = FRONTEND_DIST / "favicon.svg"
        if fav.exists():
            return FileResponse(str(fav))
        return {"message": "ok"}
    
    @app.get("/")
    async def serve_index():
        return FileResponse(str(FRONTEND_DIST / "index.html"))
    
    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        # API路径不拦截（API都有/api前缀，这里只是兜底）
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        # 尝试返回静态文件
        file_path = FRONTEND_DIST / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # SPA fallback: 其他路径返回index.html
        return FileResponse(str(FRONTEND_DIST / "index.html"))
else:
    @app.get("/")
    def root():
        return {
            "name": "谛观 GreenwashGuard",
            "version": "1.0.0",
            "docs": "/docs",
            "message": "前端未构建，请运行 npm run build 或使用 npm run dev"
        }


@app.get("/health")
def health():
    return {"status": "ok"}