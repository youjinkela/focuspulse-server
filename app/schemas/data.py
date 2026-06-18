from datetime import date, datetime
from pydantic import BaseModel


class DeviceBreakdown(BaseModel):
    device_name: str | None
    device_type: str
    focus_min: int
    efficiency: float | None = None


class OverviewResponse(BaseModel):
    total_focus_min: int
    avg_efficiency: float | None
    pomodoro_count: int
    total_pomo_min: int
    device_breakdown: list[DeviceBreakdown]


class TimelineDesktopItem(BaseModel):
    ts: str  # "HH:MM" formatted
    process: str
    category: str | None
    duration_min: int


class TimelineAndroidItem(BaseModel):
    ts: str
    app_name: str | None
    package_name: str
    category: str | None
    duration_min: int


class TimelineResponse(BaseModel):
    desktop: list[TimelineDesktopItem]
    android: list[TimelineAndroidItem]


class DailyTrend(BaseModel):
    date: date
    focus_min: int
    avg_efficiency: float | None
    pomodoro_count: int


class TrendResponse(BaseModel):
    daily: list[DailyTrend]


class AppItem(BaseModel):
    name: str
    device_type: str
    duration_min: int
    category: str | None


class AppsResponse(BaseModel):
    apps: list[AppItem]


class PomodoroHistoryItem(BaseModel):
    start_ts: datetime
    planned_duration: int
    actual_duration: int
    status: str
    focus_score: float | None
    task_name: str | None
    device_name: str | None


class PomodoroHistoryResponse(BaseModel):
    pomodoros: list[PomodoroHistoryItem]
    total: int
