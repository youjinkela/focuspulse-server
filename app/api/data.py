from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import verify_api_key
from app.models.device import Device
from app.models.window_event import WindowEvent
from app.models.session import DesktopSession
from app.models.pomodoro import PomodoroSessionCloud
from app.models.android_usage import AndroidAppUsage
from app.models.daily_summary import DailySummary
from app.schemas.data import (
    OverviewResponse, DeviceBreakdown,
    TimelineDesktopItem, TimelineAndroidItem, TimelineResponse,
    DailyTrend, TrendResponse,
    AppItem, AppsResponse,
    PomodoroHistoryItem, PomodoroHistoryResponse,
)

router = APIRouter(prefix="/api/v1/data", tags=["data"])


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    device_code: str = Query(..., min_length=6, max_length=8),
    query_date: date = Query(..., alias="date"),
    session: AsyncSession = Depends(get_session),
    _device_id=Depends(verify_api_key),
):
    # Try daily_summary cache first
    result = await session.execute(
        select(DailySummary).where(
            DailySummary.device_code == device_code,
            DailySummary.date == query_date,
        )
    )
    summary = result.scalar_one_or_none()

    if summary:
        # Get per-device breakdown
        devices_result = await session.execute(
            select(Device).where(Device.device_code == device_code)
        )
        devices = devices_result.scalars().all()

        breakdown = []
        for d in devices:
            # For desktop devices, compute focus_min from sessions
            if d.device_type == "desktop":
                sess_result = await session.execute(
                    select(func.coalesce(func.sum(DesktopSession.duration_seconds), 0))
                    .where(
                        DesktopSession.device_id == d.id,
                        func.date(DesktopSession.start_ts) == query_date,
                    )
                )
                focus_sec = sess_result.scalar() or 0
                eff_result = await session.execute(
                    select(func.avg(DesktopSession.efficiency_score))
                    .where(
                        DesktopSession.device_id == d.id,
                        func.date(DesktopSession.start_ts) == query_date,
                    )
                )
                eff = eff_result.scalar()
                breakdown.append(DeviceBreakdown(
                    device_name=d.device_name,
                    device_type="desktop",
                    focus_min=focus_sec // 60,
                    efficiency=round(eff, 1) if eff else None,
                ))
            else:
                # For android, compute from android_app_usage
                usage_result = await session.execute(
                    select(func.coalesce(func.sum(AndroidAppUsage.duration_seconds), 0))
                    .where(
                        AndroidAppUsage.device_id == d.id,
                        func.date(AndroidAppUsage.start_ts) == query_date,
                    )
                )
                focus_sec = usage_result.scalar() or 0
                breakdown.append(DeviceBreakdown(
                    device_name=d.device_name,
                    device_type="android",
                    focus_min=focus_sec // 60,
                ))

        return OverviewResponse(
            total_focus_min=summary.total_focus_min,
            avg_efficiency=round(summary.avg_efficiency, 1) if summary.avg_efficiency else None,
            pomodoro_count=summary.pomodoro_count,
            total_pomo_min=summary.total_pomo_min,
            device_breakdown=breakdown,
        )

    # Fallback: compute on the fly if no cache
    return await _compute_overview_on_fly(session, device_code, query_date)


async def _compute_overview_on_fly(
    session: AsyncSession, device_code: str, query_date: date
) -> OverviewResponse:
    """Compute overview from raw tables when cache is missing."""
    devices_result = await session.execute(
        select(Device).where(Device.device_code == device_code)
    )
    devices = devices_result.scalars().all()

    total_focus_sec = 0
    total_eff = 0.0
    eff_count = 0
    pomo_count = 0
    pomo_min = 0
    breakdown = []

    for d in devices:
        if d.device_type == "desktop":
            # Sessions
            s_result = await session.execute(
                select(
                    func.coalesce(func.sum(DesktopSession.duration_seconds), 0),
                    func.avg(DesktopSession.efficiency_score),
                ).where(
                    DesktopSession.device_id == d.id,
                    func.date(DesktopSession.start_ts) == query_date,
                )
            )
            s_row = s_result.one()
            focus_sec = s_row[0] or 0
            eff = s_row[1]
            total_focus_sec += focus_sec
            if eff:
                total_eff += eff
                eff_count += 1
            breakdown.append(DeviceBreakdown(
                device_name=d.device_name, device_type="desktop",
                focus_min=focus_sec // 60,
                efficiency=round(eff, 1) if eff else None,
            ))
        else:
            u_result = await session.execute(
                select(func.coalesce(func.sum(AndroidAppUsage.duration_seconds), 0))
                .where(
                    AndroidAppUsage.device_id == d.id,
                    func.date(AndroidAppUsage.start_ts) == query_date,
                )
            )
            focus_sec = u_result.scalar() or 0
            total_focus_sec += focus_sec
            breakdown.append(DeviceBreakdown(
                device_name=d.device_name, device_type="android",
                focus_min=focus_sec // 60,
            ))

    # Pomodoro count
    p_result = await session.execute(
        select(
            func.count(PomodoroSessionCloud.id),
            func.coalesce(func.sum(PomodoroSessionCloud.actual_duration), 0),
        ).where(
            PomodoroSessionCloud.device_id.in_(
                select(Device.id).where(Device.device_code == device_code)
            ),
            func.date(PomodoroSessionCloud.start_ts) == query_date,
            PomodoroSessionCloud.status == "completed",
        )
    )
    p_row = p_result.one()
    pomo_count = p_row[0] or 0
    pomo_min = (p_row[1] or 0) // 60

    avg_eff = round(total_eff / eff_count, 1) if eff_count > 0 else None

    return OverviewResponse(
        total_focus_min=total_focus_sec // 60,
        avg_efficiency=avg_eff,
        pomodoro_count=pomo_count,
        total_pomo_min=pomo_min,
        device_breakdown=breakdown,
    )


@router.get("/timeline", response_model=TimelineResponse)
async def get_timeline(
    device_code: str = Query(..., min_length=6, max_length=8),
    query_date: date = Query(..., alias="date"),
    limit: int = Query(200, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    _device_id=Depends(verify_api_key),
):
    # Desktop window events
    desktop = []
    w_result = await session.execute(
        select(WindowEvent, Device.device_name)
        .join(Device, WindowEvent.device_id == Device.id)
        .where(
            Device.device_code == device_code,
            func.date(WindowEvent.ts) == query_date,
        )
        .order_by(WindowEvent.ts.desc())
        .limit(limit)
    )
    for row in w_result:
        we, dev_name = row
        desktop.append(TimelineDesktopItem(
            ts=we.ts.strftime("%H:%M"),
            process=we.process,
            category=we.category,
            duration_min=round((we.duration_seconds or 0) / 60),
        ))

    # Android events
    android = []
    a_result = await session.execute(
        select(AndroidAppUsage, Device.device_name)
        .join(Device, AndroidAppUsage.device_id == Device.id)
        .where(
            Device.device_code == device_code,
            func.date(AndroidAppUsage.start_ts) == query_date,
        )
        .order_by(AndroidAppUsage.start_ts.desc())
        .limit(limit)
    )
    for row in a_result:
        au, dev_name = row
        android.append(TimelineAndroidItem(
            ts=au.start_ts.strftime("%H:%M"),
            app_name=au.app_name or au.package_name,
            package_name=au.package_name,
            category=au.category,
            duration_min=round(au.duration_seconds / 60),
        ))

    return TimelineResponse(desktop=desktop, android=android)


@router.get("/trend", response_model=TrendResponse)
async def get_trend(
    device_code: str = Query(..., min_length=6, max_length=8),
    days: int = Query(7, ge=1, le=90),
    session: AsyncSession = Depends(get_session),
    _device_id=Depends(verify_api_key),
):
    result = await session.execute(
        select(DailySummary)
        .where(
            DailySummary.device_code == device_code,
        )
        .order_by(DailySummary.date.desc())
        .limit(days)
    )
    daily = [
        DailyTrend(
            date=ds.date,
            focus_min=ds.total_focus_min,
            avg_efficiency=round(ds.avg_efficiency, 1) if ds.avg_efficiency else None,
            pomodoro_count=ds.pomodoro_count,
        )
        for ds in result.scalars().all()
    ]
    daily.reverse()  # chronological order
    return TrendResponse(daily=daily)


@router.get("/apps", response_model=AppsResponse)
async def get_apps(
    device_code: str = Query(..., min_length=6, max_length=8),
    query_date: date = Query(..., alias="date"),
    session: AsyncSession = Depends(get_session),
    _device_id=Depends(verify_api_key),
):
    # Desktop: aggregate window_events by process
    w_result = await session.execute(
        select(
            WindowEvent.process,
            func.coalesce(func.sum(WindowEvent.duration_seconds), 0),
        )
        .join(Device, WindowEvent.device_id == Device.id)
        .where(
            Device.device_code == device_code,
            func.date(WindowEvent.ts) == query_date,
        )
        .group_by(WindowEvent.process)
        .order_by(func.sum(WindowEvent.duration_seconds).desc())
    )
    apps = []
    for row in w_result:
        apps.append(AppItem(
            name=row[0],
            device_type="desktop",
            duration_min=round((row[1] or 0) / 60),
            category=None,  # would need join to classification
        ))

    # Android
    a_result = await session.execute(
        select(
            AndroidAppUsage.app_name,
            func.coalesce(func.sum(AndroidAppUsage.duration_seconds), 0),
        )
        .join(Device, AndroidAppUsage.device_id == Device.id)
        .where(
            Device.device_code == device_code,
            func.date(AndroidAppUsage.start_ts) == query_date,
        )
        .group_by(AndroidAppUsage.app_name)
        .order_by(func.sum(AndroidAppUsage.duration_seconds).desc())
    )
    for row in a_result:
        apps.append(AppItem(
            name=row[0] or "未知应用",
            device_type="android",
            duration_min=round((row[1] or 0) / 60),
            category=None,
        ))

    return AppsResponse(apps=apps)


@router.get("/pomodoros", response_model=PomodoroHistoryResponse)
async def get_pomodoros(
    device_code: str = Query(..., min_length=6, max_length=8),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _device_id=Depends(verify_api_key),
):
    # Count total
    count_result = await session.execute(
        select(func.count(PomodoroSessionCloud.id))
        .join(Device, PomodoroSessionCloud.device_id == Device.id)
        .where(Device.device_code == device_code)
    )
    total = count_result.scalar() or 0

    # Fetch page
    result = await session.execute(
        select(PomodoroSessionCloud, Device.device_name)
        .join(Device, PomodoroSessionCloud.device_id == Device.id)
        .where(Device.device_code == device_code)
        .order_by(PomodoroSessionCloud.start_ts.desc())
        .offset(offset)
        .limit(limit)
    )
    pomodoros = [
        PomodoroHistoryItem(
            start_ts=p.start_ts,
            planned_duration=p.planned_duration,
            actual_duration=p.actual_duration,
            status=p.status,
            focus_score=round(p.focus_score, 1) if p.focus_score else None,
            task_name=p.task_name,
            device_name=dev_name,
        )
        for p, dev_name in result.all()
    ]

    return PomodoroHistoryResponse(pomodoros=pomodoros, total=total)
