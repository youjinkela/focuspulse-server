from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.window_event import WindowEvent
from app.models.android_usage import AndroidAppUsage


async def purge_old_events(session: AsyncSession, retention_days: int = 30):
    """Delete window_events and android_app_usage older than retention_days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    result_we = await session.execute(
        delete(WindowEvent).where(WindowEvent.ts < cutoff)
    )
    result_au = await session.execute(
        delete(AndroidAppUsage).where(AndroidAppUsage.start_ts < cutoff)
    )
    await session.commit()

    return {
        "window_events_deleted": result_we.rowcount,
        "android_usage_deleted": result_au.rowcount,
    }
