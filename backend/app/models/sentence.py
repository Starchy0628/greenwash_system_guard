"""语句分类记录表"""
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Sentence(Base):
    __tablename__ = "sentences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_record_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("analysis_records.id"), nullable=False, index=True
    )
    sentence_text: Mapped[str] = mapped_column(Text, nullable=False)
    sentence_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deepseek_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    deepseek_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    qwen_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    qwen_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    glm_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    glm_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_category: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    vote_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # unanimous/majority/full_divergence
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_std: Mapped[float | None] = mapped_column(Float, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    review_status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # 关联
    analysis_record = relationship("AnalysisRecord", back_populates="sentences")

    def __repr__(self):
        return f"<Sentence id={self.id} category={self.final_category}>"