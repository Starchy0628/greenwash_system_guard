"""行业基准表"""
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class IndustryBenchmark(Base):
    __tablename__ = "industry_benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    industry: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    tone_median: Mapped[float | None] = mapped_column(Float, nullable=True)
    tone_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    tone_std: Mapped[float | None] = mapped_column(Float, nullable=True)
    tone_p20: Mapped[float | None] = mapped_column(Float, nullable=True)
    tone_p80: Mapped[float | None] = mapped_column(Float, nullable=True)
    gw_warn_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    def __repr__(self):
        return f"<IndustryBenchmark {self.industry} {self.year}>"