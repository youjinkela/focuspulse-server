from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import verify_api_key
from app.models.android_usage import AndroidAppUsage
from app.models.device import Device
from app.models.pomodoro import PomodoroSessionCloud
from app.models.session import DesktopSession
from app.models.window_event import WindowEvent
from app.schemas.sync import (
    AndroidUsageBatch,
    PomodoroBatch,
    SessionBatch,
    SyncResponse,
    WindowEventBatch,
)

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


async def _update_device_seen(device_id: UUID, session: AsyncSession):
    """Touch last_seen_at for the device."""
    from datetime import datetime, timezone

    await session.execute(
        update(Device).where(Device.id == device_id).values(
            last_seen_at=datetime.now(timezone.utc)
        )
    )


@router.post("/window-events", response_model=SyncResponse)
async def sync_window_events(
    batch: WindowEventBatch,
    device_id: UUID = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
):
    accepted = 0
    skipped = 0
    for evt in batch.events:
        stmt = pg_insert(WindowEvent).values(
            device_id=device_id,
            ts=evt.ts,
            process=evt.process,
            window_title=evt.window_title,
            category=evt.category,
            duration_seconds=evt.duration_seconds,
        ).on_conflict_do_nothing(
            constraint="uq_window_event"
        )
        result = await session.execute(stmt)
        if result.rowcount > 0:
            accepted += 1
        else:
            skipped += 1

    await _update_device_seen(device_id, session)
    await session.commit()
    return SyncResponse(accepted=accepted, skipped=skipped)


@router.post("/sessions", response_model=SyncResponse)
async def sync_sessions(
    batch: SessionBatch,
    device_id: UUID = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
):
    accepted = 0
    skipped = 0
    for s in batch.sessions:
        stmt = pg_insert(DesktopSession).values(
            device_id=device_id,
            start_ts=s.start_ts,
            duration_seconds=s.duration_seconds,
            main_process=s.main_process,
            efficiency_score=s.efficiency_score,
            category_scores=s.category_scores,
            audio_summary=s.audio_summary,
            switch_count=s.switch_count,
        ).on_conflict_do_nothing(constraint="uq_desktop_session")
        result = await session.execute(stmt)
        if result.rowcount > 0:
            accepted += 1
        else:
            skipped += 1

    await session.commit()
    return SyncResponse(accepted=accepted, skipped=skipped)


@router.post("/pomodoros", response_model=SyncResponse)
async def sync_pomodoros(
    batch: PomodoroBatch,
    device_id: UUID = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
):
    accepted = 0
    skipped = 0
    for p in batch.pomodoros:
        stmt = pg_insert(PomodoroSessionCloud).values(
            device_id=device_id,
            start_ts=p.start_ts,
            planned_duration=p.planned_duration,
            actual_duration=p.actual_duration,
            status=p.status,
            focus_score=p.focus_score,
            task_name=p.task_name,
            interruptions=p.interruptions,
        ).on_conflict_do_nothing(constraint="uq_pomodoro_cloud")
        result = await session.execute(stmt)
        if result.rowcount > 0:
            accepted += 1
        else:
            skipped += 1

    await session.commit()
    return SyncResponse(accepted=accepted, skipped=skipped)


@router.post("/app-usage", response_model=SyncResponse)
async def sync_app_usage(
    batch: AndroidUsageBatch,
    device_id: UUID = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
):
    accepted = 0
    skipped = 0
    for u in batch.usage:
        stmt = pg_insert(AndroidAppUsage).values(
            device_id=device_id,
            start_ts=u.start_ts,
            duration_seconds=u.duration_seconds,
            package_name=u.package_name,
            app_name=u.app_name,
            category=u.category,
        ).on_conflict_do_nothing(constraint="uq_android_usage")
        result = await session.execute(stmt)
        if result.rowcount > 0:
            accepted += 1
        else:
            skipped += 1

    await session.commit()
    return SyncResponse(accepted=accepted, skipped=skipped)
