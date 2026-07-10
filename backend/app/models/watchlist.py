"""关注列表"""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Watchlist(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), unique=True, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 关联
    company = relationship("Company", back_populates="watchlist_entry")

    def __repr__(self):
        return f"<Watchlist company_id={self.company_id}>"