"""数据库连接管理 — SQLAlchemy 2.0（支持 SQLite / PostgreSQL 双模式）"""
import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import get_settings

settings = get_settings()

db_url = settings.database_url
_is_postgresql = db_url.startswith("postgresql")

# ---------- 处理 SQLite 相对路径 ----------
if db_url.startswith("sqlite:///./"):
    rel = db_url[len("sqlite:///./"):]
    abs_path = Path(__file__).resolve().parent.parent.parent.parent / rel
    db_url = f"sqlite:///{abs_path}"

# ---------- 创建引擎 ----------
if _is_postgresql:
    engine = create_engine(
        db_url,
        echo=False,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
else:
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """创建所有表"""
    from app.models import company, analysis, sentence, industry, watchlist  # noqa
    Base.metadata.create_all(bind=engine)


def get_db_url_info() -> dict:
    """获取当前数据库连接信息（用于调试）"""
    if _is_postgresql:
        return {
            "type": "postgresql",
            "url": db_url.replace(settings.db_password, "***") if settings.db_password else db_url,
            "pool_size": settings.db_pool_size,
        }
    return {
        "type": "sqlite",
        "url": db_url,
    }