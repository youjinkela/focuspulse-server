from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from logging import getLogger

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from sqlalchemy import text

from app.api.data import router as data_router
from app.api.pairing import router as pairing_router
from app.api.sync import router as sync_router
from app.config import settings
from app.database import async_session_factory

logger = getLogger(__name__)


async def _run_daily_aggregation(target_date: date | None = None):
    """Compute daily summaries for all active codes."""
    from app.database import async_session_factory
    from app.services.aggregation import compute_all_active_codes

    if target_date is None:
        target_date = date.today()

    async with async_session_factory() as session:
        codes = await compute_all_active_codes(session, target_date)
        logger.info(f"Daily aggregation complete for {target_date}: {len(codes)} codes")


async def _run_cleanup():
    """Purge window_events and android_app_usage older than 30 days."""
    from app.database import async_session_factory
    from app.services.cleanup import purge_old_events

    async with async_session_factory() as session:
        result = await purge_old_events(session)
        logger.info(f"Data cleanup: {result}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup: verify DB connection, start scheduler
    async with async_session_factory() as session:
        await session.execute(text("SELECT 1"))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_daily_aggregation,
        "cron",
        hour=settings.daily_summary_hour,
        minute=0,
        args=[date.today()],
    )
    scheduler.add_job(
        _run_cleanup,
        "cron",
        hour=3,
        minute=0,  # 3:00 UTC daily
    )
    scheduler.start()
    logger.info(f"Daily aggregation scheduled for hour {settings.daily_summary_hour}:00 UTC")
    yield
    scheduler.shutdown()
    from app.database import engine
    await engine.dispose()


app = FastAPI(
    title="FocusPulse API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(pairing_router)
app.include_router(sync_router)
app.include_router(data_router)


@app.get("/health")
async def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/health")
async def api_health():
    return {"status": "ok", "version": "0.1.0"}
