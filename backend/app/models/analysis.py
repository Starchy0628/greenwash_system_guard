"""企业年度分析记录表"""
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class AnalysisRecord(Base):
    __tablename__ = "analysis_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    data_source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # MDA
    source_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_sentences: Mapped[int] = mapped_column(Integer, default=0)
    env_sentences: Mapped[int] = mapped_column(Integer, default=0)
    substantive_count: Mapped[int] = mapped_column(Integer, default=0)
    descriptive_count: Mapped[int] = mapped_column(Integer, default=0)
    non_env_count: Mapped[int] = mapped_column(Integer, default=0)
    tone_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    industry_median_tone: Mapped[float | None] = mapped_column(Float, nullable=True)
    gw_index: Mapped[float | None] = mapped_column(Float, index=True, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(10), default="正常", index=True)  # 正常 / 预警
    fleiss_kappa: Mapped[float | None] = mapped_column(Float, nullable=True)
    dispute_count: Mapped[int] = mapped_column(Integer, default=0)
    analysis_status: Mapped[str] = mapped_column(String(20), default="completed", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # 关联
    company = relationship("Company", back_populates="analysis_records")
    sentences = relationship("Sentence", back_populates="analysis_record", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AnalysisRecord company={self.company_id} year={self.year} gw={self.gw_index}>"