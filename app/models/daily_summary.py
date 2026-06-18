import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Date, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DailySummary(Base):
    __tablename__ = "daily_summary"
    __table_args__ = (
        UniqueConstraint("device_code", "date", name="uq_daily_summary"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_code: Mapped[str] = mapped_column(String(8), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    total_focus_min: Mapped[int] = mapped_column(Integer, default=0)
    avg_efficiency: Mapped[float | None] = mapped_column(Float)
    pomodoro_count: Mapped[int] = mapped_column(Integer, default=0)
    total_pomo_min: Mapped[int] = mapped_column(Integer, default=0)
    top_apps: Mapped[dict | None] = mapped_column(JSONB)
    category_breakdown: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
