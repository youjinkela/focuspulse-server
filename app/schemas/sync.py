from datetime import datetime

from pydantic import BaseModel, Field


class WindowEventItem(BaseModel):
    ts: datetime
    process: str = Field(..., max_length=255)
    window_title: str | None = Field(None, max_length=500)
    category: str | None = Field(None, pattern="^(high|medium|low)?$")
    duration_seconds: int | None = None


class WindowEventBatch(BaseModel):
    events: list[WindowEventItem]


class SessionItem(BaseModel):
    start_ts: datetime
    duration_seconds: int = 300
    main_process: str | None = Field(None, max_length=255)
    efficiency_score: float | None = None
    category_scores: dict | None = None
    audio_summary: dict | None = None
    switch_count: int | None = 0


class SessionBatch(BaseModel):
    sessions: list[SessionItem]


class PomodoroItem(BaseModel):
    start_ts: datetime
    planned_duration: int
    actual_duration: int
    status: str = Field(..., pattern="^(completed|cancelled)$")
    focus_score: float | None = None
    task_name: str | None = Field(None, max_length=255)
    interruptions: list | None = None


class PomodoroBatch(BaseModel):
    pomodoros: list[PomodoroItem]


class AndroidUsageItem(BaseModel):
    start_ts: datetime
    duration_seconds: int
    package_name: str = Field(..., max_length=255)
    app_name: str | None = Field(None, max_length=255)
    category: str | None = Field(None, pattern="^(high|medium|low)?$")


class AndroidUsageBatch(BaseModel):
    usage: list[AndroidUsageItem]


class SyncResponse(BaseModel):
    accepted: int
    skipped: int = 0
