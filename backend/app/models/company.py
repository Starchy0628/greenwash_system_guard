"""企业基础信息表"""
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

# 金融类行业（需在所有分析中剔除）
FINANCIAL_INDUSTRIES = ["银行", "非银金融"]


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(100), nullable=False)
    industry: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    short_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_a_share: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_st: Mapped[bool] = mapped_column(Boolean, default=False, index=True)  # ST / *ST / PT
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # 关联
    analysis_records = relationship("AnalysisRecord", back_populates="company")
    watchlist_entry = relationship("Watchlist", back_populates="company", uselist=False)

    def __repr__(self):
        return f"<Company {self.stock_code} {self.company_name}>"