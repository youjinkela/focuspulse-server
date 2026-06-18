import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DesktopSession(Base):
    __tablename__ = "desktop_sessions"
    __table_args__ = (
        UniqueConstraint("device_id", "start_ts", name="uq_desktop_session"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    start_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    main_process: Mapped[str | None] = mapped_column(String(255))
    efficiency_score: Mapped[float | None] = mapped_column(Float)
    category_scores: Mapped[dict | None] = mapped_column(JSONB)
    audio_summary: Mapped[dict | None] = mapped_column(JSONB)
    switch_count: Mapped[int | None] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
