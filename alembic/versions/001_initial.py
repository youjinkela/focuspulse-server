"""initial migration: create all tables

Revision ID: 001
Revises:
Create Date: 2026-06-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- devices ---
    op.create_table(
        "devices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("device_code", sa.String(8), nullable=False, index=True),
        sa.Column("device_name", sa.String(100), nullable=True),
        sa.Column("device_type", sa.String(20), nullable=False),
        sa.Column("platform_info", JSONB, nullable=True),
        sa.Column("api_key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    # --- window_events ---
    op.create_table(
        "window_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("device_id", UUID(as_uuid=True), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("process", sa.String(255), nullable=False),
        sa.Column("window_title", sa.String(500), nullable=True),
        sa.Column("category", sa.String(20), nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("device_id", "ts", "process", name="uq_window_event"),
    )
    op.create_index(op.f("ix_window_events_device_id"), "window_events", ["device_id"])

    # --- desktop_sessions ---
    op.create_table(
        "desktop_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("device_id", UUID(as_uuid=True), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("start_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer, nullable=False, server_default=sa.text("300")),
        sa.Column("main_process", sa.String(255), nullable=True),
        sa.Column("efficiency_score", sa.Float, nullable=True),
        sa.Column("category_scores", JSONB, nullable=True),
        sa.Column("audio_summary", JSONB, nullable=True),
        sa.Column("switch_count", sa.Integer, nullable=True, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("device_id", "start_ts", name="uq_desktop_session"),
    )
    op.create_index(op.f("ix_desktop_sessions_device_id"), "desktop_sessions", ["device_id"])

    # --- pomodoro_sessions_cloud ---
    op.create_table(
        "pomodoro_sessions_cloud",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("device_id", UUID(as_uuid=True), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("start_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("planned_duration", sa.Integer, nullable=False),
        sa.Column("actual_duration", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("focus_score", sa.Float, nullable=True),
        sa.Column("task_name", sa.String(255), nullable=True),
        sa.Column("interruptions", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("device_id", "start_ts", name="uq_pomodoro_cloud"),
    )
    op.create_index(op.f("ix_pomodoro_sessions_cloud_device_id"), "pomodoro_sessions_cloud", ["device_id"])

    # --- android_app_usage ---
    op.create_table(
        "android_app_usage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("device_id", UUID(as_uuid=True), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("start_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer, nullable=False),
        sa.Column("package_name", sa.String(255), nullable=False),
        sa.Column("app_name", sa.String(255), nullable=True),
        sa.Column("category", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("device_id", "start_ts", "package_name", name="uq_android_usage"),
    )
    op.create_index(op.f("ix_android_app_usage_device_id"), "android_app_usage", ["device_id"])

    # --- daily_summary ---
    op.create_table(
        "daily_summary",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("device_code", sa.String(8), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("total_focus_min", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("avg_efficiency", sa.Float, nullable=True),
        sa.Column("pomodoro_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("total_pomo_min", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("top_apps", JSONB, nullable=True),
        sa.Column("category_breakdown", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("device_code", "date", name="uq_daily_summary"),
    )

    # --- pairing_codes ---
    op.create_table(
        "pairing_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("device_code", sa.String(8), nullable=False, unique=True),
        sa.Column("owner_device", UUID(as_uuid=True), sa.ForeignKey("devices.id"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("pairing_codes")
    op.drop_table("daily_summary")
    op.drop_table("android_app_usage")
    op.drop_table("pomodoro_sessions_cloud")
    op.drop_table("desktop_sessions")
    op.drop_table("window_events")
    op.drop_table("devices")
