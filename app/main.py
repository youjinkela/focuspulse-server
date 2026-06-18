from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from sqlalchemy import text

from app.database import async_session_factory


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup: verify DB connection
    async with async_session_factory() as session:
        await session.execute(text("SELECT 1"))
    yield
    # Shutdown: dispose engine
    from app.database import engine
    await engine.dispose()


app = FastAPI(
    title="FocusPulse API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/health")
async def api_health():
    return {"status": "ok", "version": "0.1.0"}
