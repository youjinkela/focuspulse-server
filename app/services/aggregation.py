from datetime import date, datetime, timezone
from logging import getLogger

from sqlalchemy import Integer, cast, select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.window_event import WindowEvent
from app.models.session import DesktopSession
from app.models.pomodoro import PomodoroSessionCloud
from app.models.android_usage import AndroidAppUsage
from app.models.daily_summary import DailySummary

logger = getLogger(__name__)


async def compute_daily_summary(
    session: AsyncSession,
    device_code: str,
    target_date: date,
) -> DailySummary:
    """Compute and upsert daily_summary for a given device_code and date."""
    # Get all devices under this code
    devices_result = await session.execute(
        select(Device).where(Device.device_code == device_code)
    )
    devices = devices_result.scalars().all()
    device_ids = [d.id for d in devices]

    if not device_ids:
        raise ValueError(f"No devices found for code: {device_code}")

    # Total focus time (desktop sessions + android usage)
    focus_sec = 0

    # Desktop sessions
    s_result = await session.execute(
        select(func.coalesce(func.sum(DesktopSession.duration_seconds), 0))
        .where(
            DesktopSession.device_id.in_(device_ids),
            func.date(DesktopSession.start_ts) == target_date,
        )
    )
    focus_sec += s_result.scalar() or 0

    # Android usage
    a_result = await session.execute(
        select(func.coalesce(func.sum(AndroidAppUsage.duration_seconds), 0))
        .where(
            AndroidAppUsage.device_id.in_(device_ids),
            func.date(AndroidAppUsage.start_ts) == target_date,
        )
    )
    focus_sec += a_result.scalar() or 0

    # Average efficiency
    eff_result = await session.execute(
        select(func.avg(DesktopSession.efficiency_score))
        .where(
            DesktopSession.device_id.in_(device_ids),
            func.date(DesktopSession.start_ts) == target_date,
        )
    )
    avg_eff = eff_result.scalar()

    # Pomodoro count
    p_result = await session.execute(
        select(
            func.count(PomodoroSessionCloud.id),
            func.coalesce(func.sum(PomodoroSessionCloud.actual_duration), 0),
        )
        .where(
            PomodoroSessionCloud.device_id.in_(device_ids),
            func.date(PomodoroSessionCloud.start_ts) == target_date,
            PomodoroSessionCloud.status == "completed",
        )
    )
    p_row = p_result.one()
    pomo_count = p_row[0] or 0
    pomo_min = (p_row[1] or 0) // 60

    # Top apps (desktop)
    top_result = await session.execute(
        select(
            WindowEvent.process,
            func.coalesce(func.sum(WindowEvent.duration_seconds), 0).label("total_sec"),
        )
        .where(
            WindowEvent.device_id.in_(device_ids),
            func.date(WindowEvent.ts) == target_date,
        )
        .group_by(WindowEvent.process)
        .order_by(func.sum(WindowEvent.duration_seconds).desc())
        .limit(10)
    )
    top_apps = {row.process: (row.total_sec or 0) // 60 for row in top_result}

    # Category breakdown (desktop sessions)
    cat_result = await session.execute(
        select(
            func.sum(
                cast(
                    func.jsonb_extract_path_text(
                        DesktopSession.category_scores, "high"
                    ),
                    Integer,
                )
            ),
            func.sum(
                cast(
                    func.jsonb_extract_path_text(
                        DesktopSession.category_scores, "medium"
                    ),
                    Integer,
                )
            ),
            func.sum(
                cast(
                    func.jsonb_extract_path_text(
                        DesktopSession.category_scores, "low"
                    ),
                    Integer,
                )
            ),
        ).where(
            DesktopSession.device_id.in_(device_ids),
            func.date(DesktopSession.start_ts) == target_date,
        )
    )
    cat_row = cat_result.one()
    category_breakdown = {
        "high": cat_row[0] or 0,
        "medium": cat_row[1] or 0,
        "low": cat_row[2] or 0,
    }

    # Upsert
    stmt = pg_insert(DailySummary).values(
        device_code=device_code,
        date=target_date,
        total_focus_min=focus_sec // 60,
        avg_efficiency=round(avg_eff, 1) if avg_eff else None,
        pomodoro_count=pomo_count,
        total_pomo_min=pomo_min,
        top_apps=top_apps,
        category_breakdown=category_breakdown,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_daily_summary",
        set_={
            "total_focus_min": stmt.excluded.total_focus_min,
            "avg_efficiency": stmt.excluded.avg_efficiency,
            "pomodoro_count": stmt.excluded.pomodoro_count,
            "total_pomo_min": stmt.excluded.total_pomo_min,
            "top_apps": stmt.excluded.top_apps,
            "category_breakdown": stmt.excluded.category_breakdown,
            "updated_at": datetime.now(timezone.utc),
        },
    )
    await session.execute(stmt)
    await session.commit()

    # Return the saved record
    result = await session.execute(
        select(DailySummary).where(
            DailySummary.device_code == device_code,
            DailySummary.date == target_date,
        )
    )
    return result.scalar_one()


async def compute_all_active_codes(session: AsyncSession, target_date: date | None = None) -> list[str]:
    """Compute daily summaries for all active device codes."""
    if target_date is None:
        target_date = date.today()

    # Get distinct device codes
    result = await session.execute(
        select(Device.device_code).distinct()
    )
    codes = result.scalars().all()

    computed = []
    for code in codes:
        try:
            await compute_daily_summary(session, code, target_date)
            computed.append(code)
        except Exception as e:
            logger.warning(f"Daily aggregation failed for device_code {code}: {e}")

    return computed
