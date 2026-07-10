"""数据库连接管理 — SQLAlchemy 2.0"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import get_settings

settings = get_settings()

# 处理 SQLite 相对路径
db_url = settings.database_url
if db_url.startswith("sqlite:///./"):
    import os
    from pathlib import Path
    rel = db_url[len("sqlite:///./"):]
    abs_path = Path(__file__).resolve().parent.parent.parent.parent / rel
    db_url = f"sqlite:///{abs_path}"

engine = create_engine(
    db_url,
    connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
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