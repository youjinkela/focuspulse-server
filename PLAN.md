# FocusPulse Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Build the FastAPI + PostgreSQL backend for FocusPulse cloud sync — device pairing, data sync APIs, and data query APIs.

**Architecture:** Async FastAPI with SQLAlchemy 2.0 async ORM (asyncpg driver), Alembic for migrations, API Key bearer auth, Pydantic v2 schemas. Deployed as a single Docker container to Railway/Render.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, asyncpg, Alembic, pytest + httpx

## Global Constraints

- Python >= 3.12
- All timestamps in ISO 8601 with timezone offset (RFC 3339)
- UUID primary keys on all tables (use `gen_random_uuid()`)
- API base path: `/api/v1/`
- All API responses follow `{"data": ..., "error": ..., "code": ...}` envelope
- API Key transmitted via `Authorization: Bearer <key>` header
- Device pairing codes: 6-character alphanumeric uppercase (excluding 0/O/I/L for readability)
- Tests use httpx AsyncClient with FastAPI's TestClient (asgi-transport)
- Database URL configured via `DATABASE_URL` env var

---

### Task 1: Project Scaffolding + Config + Health Check

**Files:**
- Create: `D:\xm\focuspulse-server\pyproject.toml`
- Create: `D:\xm\focuspulse-server\app\__init__.py`
- Create: `D:\xm\focuspulse-server\app\config.py`
- Create: `D:\xm\focuspulse-server\app\main.py`
- Create: `D:\xm\focuspulse-server\app\database.py`
- Create: `D:\xm\focuspulse-server\tests\__init__.py`
- Create: `D:\xm\focuspulse-server\tests\conftest.py`

**Interfaces:**
- Produces: `app.main:app` — FastAPI ASGI app with `/health` endpoint
- Produces: `app.config.settings` — Pydantic `BaseSettings` from env vars
- Produces: `app.database.engine`, `app.database.AsyncSession` — async SQLAlchemy
- Produces: `tests.conftest.async_client` — pytest fixture for httpx async tests

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "focuspulse-server"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "alembic>=1.13",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",
]

[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.backends._legacy:_Backend"
```

- [ ] **Step 2: Create app/__init__.py** (empty)

- [ ] **Step 3: Create app/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/focuspulse"
    sync_secret_key: str = "change-me-in-production"
    device_code_length: int = 6
    daily_summary_hour: int = 2  # UTC hour to run daily aggregation

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
```

- [ ] **Step 4: Create app/database.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:  # type: ignore[misc]
    async with async_session_factory() as session:
        yield session
```

- [ ] **Step 5: Create app/main.py**

```python
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
```

- [ ] **Step 6: Create tests/__init__.py** (empty)

- [ ] **Step 7: Create tests/conftest.py**

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def db_session():
    """Override with test DB in Task 2."""
    return None
```

- [ ] **Step 8: Verify scaffolding works**

```bash
cd D:\xm\focuspulse-server
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\pytest -x -v
```

Expected: 0 tests collected (no test files with actual tests yet), but import succeeds.

Then verify the app starts:
```bash
.venv\Scripts\python -c "from app.main import app; print(f'App loaded: {app.title}')"
```

Expected: `App loaded: FocusPulse API`

---

### Task 2: Database Models + Alembic

**Files:**
- Create: `D:\xm\focuspulse-server\app\models\__init__.py`
- Create: `D:\xm\focuspulse-server\app\models\device.py`
- Create: `D:\xm\focuspulse-server\app\models\window_event.py`
- Create: `D:\xm\focuspulse-server\app\models\session.py`
- Create: `D:\xm\focuspulse-server\app\models\pomodoro.py`
- Create: `D:\xm\focuspulse-server\app\models\android_usage.py`
- Create: `D:\xm\focuspulse-server\app\models\daily_summary.py`
- Create: `D:\xm\focuspulse-server\app\models\pairing_code.py`
- Create: `D:\xm\focuspulse-server\alembic.ini`
- Create: `D:\xm\focuspulse-server\alembic\env.py`
- Create: `D:\xm\focuspulse-server\alembic\script.py.mako`
- Create: `D:\xm\focuspulse-server\alembic\versions\.gitkeep`

**Interfaces:**
- Produces: All SQLAlchemy model classes, ready for alembic autogenerate
- Produces: `app.models.__init__.Base` re-export
- Consumes: `app.database.Base`

- [ ] **Step 1: Create app/models/__init__.py**

```python
from app.database import Base
from app.models.device import Device
from app.models.window_event import WindowEvent
from app.models.session import DesktopSession
from app.models.pomodoro import PomodoroSessionCloud
from app.models.android_usage import AndroidAppUsage
from app.models.daily_summary import DailySummary
from app.models.pairing_code import PairingCode

__all__ = [
    "Base",
    "Device",
    "WindowEvent",
    "DesktopSession",
    "PomodoroSessionCloud",
    "AndroidAppUsage",
    "DailySummary",
    "PairingCode",
]
```

- [ ] **Step 2: Create app/models/device.py**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    device_name: Mapped[str | None] = mapped_column(String(100))
    device_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "desktop" | "android"
    platform_info: Mapped[dict | None] = mapped_column(JSONB)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 3: Create app/models/window_event.py**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WindowEvent(Base):
    __tablename__ = "window_events"
    __table_args__ = (
        UniqueConstraint("device_id", "ts", "process", name="uq_window_event"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    process: Mapped[str] = mapped_column(String(255), nullable=False)
    window_title: Mapped[str | None] = mapped_column(String(500))
    category: Mapped[str | None] = mapped_column(String(20))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 4: Create app/models/session.py**

```python
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
```

- [ ] **Step 5: Create app/models/pomodoro.py**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PomodoroSessionCloud(Base):
    __tablename__ = "pomodoro_sessions_cloud"
    __table_args__ = (
        UniqueConstraint("device_id", "start_ts", name="uq_pomodoro_cloud"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    start_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_duration: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_duration: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    focus_score: Mapped[float | None] = mapped_column(Float)
    task_name: Mapped[str | None] = mapped_column(String(255))
    interruptions: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 6: Create app/models/android_usage.py**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AndroidAppUsage(Base):
    __tablename__ = "android_app_usage"
    __table_args__ = (
        UniqueConstraint("device_id", "start_ts", "package_name", name="uq_android_usage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    start_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    package_name: Mapped[str] = mapped_column(String(255), nullable=False)
    app_name: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 7: Create app/models/daily_summary.py**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Date, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DailySummary(Base):
    __tablename__ = "daily_summary"
    __table_args__ = (
        UniqueConstraint("device_code", "date", name="uq_daily_summary"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_code: Mapped[str] = mapped_column(String(8), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    total_focus_min: Mapped[int] = mapped_column(Integer, default=0)
    avg_efficiency: Mapped[float | None] = mapped_column(Float)
    pomodoro_count: Mapped[int] = mapped_column(Integer, default=0)
    total_pomo_min: Mapped[int] = mapped_column(Integer, default=0)
    top_apps: Mapped[dict | None] = mapped_column(JSONB)
    category_breakdown: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 8: Create app/models/pairing_code.py**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PairingCode(Base):
    __tablename__ = "pairing_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_code: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)
    owner_device: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 9: Set up Alembic**

Create `alembic.ini`:
```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://localhost:5432/focuspulse

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Create `alembic/env.py`:
```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import Base
from app.models import *  # noqa: F401, F403 — ensures all models loaded
from app.config import settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(settings.database_url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Create `alembic/script.py.mako`:
```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 10: Verify models import and Alembic can generate migration**

First verify models import correctly:
```bash
cd D:\xm\focuspulse-server
.venv\Scripts\python -c "from app.models import *; print('Models loaded:', [c.__tablename__ for c in Base.__subclasses__()])"
```

Expected:
```
Models loaded: ['devices', 'window_events', 'desktop_sessions', 'pomodoro_sessions_cloud', 'android_app_usage', 'daily_summary', 'pairing_codes']
```

Then verify alembic can autogenerate (requires a real Postgres — skip if no DB available):
```bash
.venv\Scripts\alembic revision --autogenerate -m "initial"
```

Expected: Creates `alembic/versions/<hash>_initial.py` with all table definitions.

---

### Task 3: API Key Auth Middleware

**Files:**
- Create: `D:\xm\focuspulse-server\app\dependencies.py`
- Modify: `D:\xm\focuspulse-server\app\config.py`

**Interfaces:**
- Produces: `app.dependencies.verify_api_key` — FastAPI dependency that returns `device_id: UUID`
- Produces: `app.dependencies.hash_api_key(raw: str) -> str`
- Produces: `app.dependencies.generate_api_key() -> str`

- [ ] **Step 1: Add hashlib utility to config**

Modify `app/config.py`, add import and method:
```python
import hashlib
import secrets
import string


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/focuspulse"
    sync_secret_key: str = "change-me-in-production"
    device_code_length: int = 6
    daily_summary_hour: int = 2


settings = Settings()


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(f"{settings.sync_secret_key}:{raw}".encode()).hexdigest()


def generate_api_key() -> str:
    return "fp_" + secrets.token_hex(24)


def generate_device_code() -> str:
    alphabet = string.ascii_uppercase.replace("O", "").replace("I", "").replace("L", "") + string.digits
    # Remove 0 from digits
    alphabet = alphabet.replace("0", "")
    return "".join(secrets.choice(alphabet) for _ in range(settings.device_code_length))
```

- [ ] **Step 2: Create app/dependencies.py**

```python
from uuid import UUID

from fastapi import Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import hash_api_key
from app.database import get_session
from app.models.device import Device


async def verify_api_key(
    authorization: str = Header(..., description="Bearer <api_key>"),
    session: AsyncSession = get_session,
) -> UUID:
    """FastAPI dependency. Extracts API Key, looks up device, returns device_id."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    raw_key = authorization.removeprefix("Bearer ").strip()
    if not raw_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    key_hash = hash_api_key(raw_key)
    result = await session.execute(select(Device).where(Device.api_key_hash == key_hash))
    device = result.scalar_one_or_none()

    if device is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return device.id
```

- [ ] **Step 3: Write test and verify**

```python
# tests/test_auth.py
import pytest
from app.config import hash_api_key, generate_api_key, generate_device_code


class TestCrypto:
    def test_generate_api_key_format(self):
        key = generate_api_key()
        assert key.startswith("fp_")
        assert len(key) == 51  # "fp_" + 48 hex chars

    def test_hash_api_key_deterministic(self):
        key = "test_key_123"
        h1 = hash_api_key(key)
        h2 = hash_api_key(key)
        assert h1 == h2
        assert len(h1) == 64  # sha256 hex

    def test_hash_different_keys(self):
        assert hash_api_key("key_a") != hash_api_key("key_b")

    def test_generate_device_code_length(self):
        code = generate_device_code()
        assert len(code) == 6
        assert code.isalnum()

    def test_generate_device_code_excludes_confusables(self):
        for _ in range(100):
            code = generate_device_code()
            for ch in code:
                assert ch not in "0OIL", f"Contains confusable: {ch}"
```

Run:
```bash
cd D:\xm\focuspulse-server
.venv\Scripts\pytest tests/test_auth.py -v
```

Expected: All 5 tests PASS.

---

### Task 4: Pairing API

**Files:**
- Create: `D:\xm\focuspulse-server\app\schemas\__init__.py`
- Create: `D:\xm\focuspulse-server\app\schemas\pairing.py`
- Create: `D:\xm\focuspulse-server\app\services\__init__.py`
- Create: `D:\xm\focuspulse-server\app\services\pairing.py`
- Create: `D:\xm\focuspulse-server\app\api\__init__.py`
- Create: `D:\xm\focuspulse-server\app\api\pairing.py`
- Modify: `D:\xm\focuspulse-server\app\main.py` (register router)
- Create: `D:\xm\focuspulse-server\tests\test_pairing.py`

**Interfaces:**
- Consumes: `app.dependencies.verify_api_key`
- Consumes: `app.models.*` (all model classes)
- Consumes: `app.config.generate_api_key`, `app.config.hash_api_key`, `app.config.generate_device_code`
- Produces: `app.api.pairing.router` — FastAPI APIRouter with `/api/v1/pairing/*`

- [ ] **Step 1: Create app/schemas/__init__.py** (empty)

- [ ] **Step 2: Create app/schemas/pairing.py**

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    device_name: str = Field(..., max_length=100)
    device_type: str = Field(..., pattern="^(desktop|android)$")
    platform: dict | None = None


class RegisterResponse(BaseModel):
    device_id: UUID
    device_code: str
    api_key: str


class VerifyRequest(BaseModel):
    device_code: str = Field(..., min_length=6, max_length=8)
    device_name: str = Field(..., max_length=100)
    device_type: str = Field(..., pattern="^(desktop|android)$")
    platform: dict | None = None


class DeviceInfo(BaseModel):
    device_id: UUID
    device_name: str | None
    device_type: str
    last_seen_at: datetime | None


class VerifyResponse(BaseModel):
    device_id: UUID
    api_key: str
    existing_devices: list[DeviceInfo]


class PairingStatus(BaseModel):
    device_code: str
    devices: list[DeviceInfo]
    paired_count: int
```

- [ ] **Step 3: Create app/services/__init__.py** (empty)

- [ ] **Step 4: Create app/services/pairing.py**

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import generate_api_key, hash_api_key, generate_device_code
from app.models.device import Device
from app.models.pairing_code import PairingCode


async def register_device(
    session: AsyncSession,
    device_name: str,
    device_type: str,
    platform: dict | None,
) -> dict:
    """Register the first device and create a pairing code."""
    api_key = generate_api_key()
    device = Device(
        device_code="",  # placeholder, will update after code generation
        device_name=device_name,
        device_type=device_type,
        platform_info=platform,
        api_key_hash=hash_api_key(api_key),
        last_seen_at=datetime.now(timezone.utc),
    )
    session.add(device)
    await session.flush()  # get device.id

    code = generate_device_code()
    device.device_code = code

    pairing = PairingCode(
        device_code=code,
        owner_device=device.id,
        is_active=True,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    session.add(pairing)
    await session.commit()

    return {"device_id": device.id, "device_code": code, "api_key": api_key}


async def verify_code(
    session: AsyncSession,
    device_code: str,
    device_name: str,
    device_type: str,
    platform: dict | None,
) -> dict:
    """Verify a pairing code and join the device group."""
    result = await session.execute(
        select(PairingCode).where(
            PairingCode.device_code == device_code,
            PairingCode.is_active == True,  # noqa: E712
        )
    )
    pairing = result.scalar_one_or_none()

    if pairing is None or (pairing.expires_at and pairing.expires_at < datetime.now(timezone.utc)):
        raise ValueError("Invalid or expired pairing code")

    api_key = generate_api_key()
    device = Device(
        device_code=device_code,
        device_name=device_name,
        device_type=device_type,
        platform_info=platform,
        api_key_hash=hash_api_key(api_key),
        last_seen_at=datetime.now(timezone.utc),
    )
    session.add(device)
    await session.flush()

    # Fetch existing devices under this code
    result = await session.execute(
        select(Device).where(
            Device.device_code == device_code,
            Device.id != device.id,
        )
    )
    existing = result.scalars().all()

    await session.commit()

    return {
        "device_id": device.id,
        "api_key": api_key,
        "existing_devices": [
            {"device_id": d.id, "device_name": d.device_name, "device_type": d.device_type, "last_seen_at": d.last_seen_at}
            for d in existing
        ],
    }


async def get_pairing_status(session: AsyncSession, device_code: str) -> dict:
    result = await session.execute(
        select(Device).where(Device.device_code == device_code)
    )
    devices = result.scalars().all()
    return {
        "device_code": device_code,
        "devices": [
            {"device_id": d.id, "device_name": d.device_name, "device_type": d.device_type, "last_seen_at": d.last_seen_at}
            for d in devices
        ],
        "paired_count": len(devices),
    }
```

- [ ] **Step 5: Create app/api/__init__.py** (empty)

- [ ] **Step 6: Create app/api/pairing.py**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import verify_api_key
from app.schemas.pairing import RegisterRequest, RegisterResponse, VerifyRequest, VerifyResponse, PairingStatus
from app.services.pairing import register_device, verify_code, get_pairing_status

router = APIRouter(prefix="/api/v1/pairing", tags=["pairing"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(req: RegisterRequest, session: AsyncSession = Depends(get_session)):
    try:
        result = await register_device(session, req.device_name, req.device_type, req.platform)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify", response_model=VerifyResponse)
async def verify(req: VerifyRequest, session: AsyncSession = Depends(get_session)):
    try:
        result = await verify_code(session, req.device_code, req.device_name, req.device_type, req.platform)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/status", response_model=PairingStatus)
async def status(
    device_code: str = Query(..., min_length=6, max_length=8),
    session: AsyncSession = Depends(get_session),
    _device_id=Depends(verify_api_key),
):
    try:
        return await get_pairing_status(session, device_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 7: Register router in app/main.py**

Modify `app/main.py`:
```python
from app.api.pairing import router as pairing_router

# After creating the app
app.include_router(pairing_router)
```

- [ ] **Step 8: Write tests for pairing API**

Create `tests/test_pairing.py`:
```python
import pytest
from httpx import AsyncClient


class TestPairingAPI:
    """Integration tests using a shared test DB.
    
    NOTE: These tests require a running PostgreSQL.
    For CI/local, set DATABASE_URL env var to test DB.
    Skip with `@pytest.mark.skipif` if no DB available.
    """

    @pytest.mark.skip(reason="Requires PostgreSQL — run manually")
    async def test_register_and_verify_flow(self, async_client: AsyncClient):
        # Register first device
        resp = await async_client.post("/api/v1/pairing/register", json={
            "device_name": "测试电脑",
            "device_type": "desktop",
            "platform": {"os": "Windows 11"},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "device_code" in data
        assert data["device_code"]  # non-empty
        assert data["api_key"].startswith("fp_")

        device_code = data["device_code"]

        # Verify second device uses same code
        resp2 = await async_client.post("/api/v1/pairing/verify", json={
            "device_code": device_code,
            "device_name": "测试手机",
            "device_type": "android",
        })
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["api_key"].startswith("fp_")
        assert len(data2["existing_devices"]) == 1
        assert data2["existing_devices"][0]["device_name"] == "测试电脑"
```

- [ ] **Step 9: Verify the router is registered**

```bash
cd D:\xm\focuspulse-server
.venv\Scripts\python -c "
from app.main import app
routes = [(r.path, r.methods) for r in app.routes]
print('\n'.join(f'{p} {m}' for p, m in routes))
"
```

Expected output includes:
```
/api/v1/pairing/register {'POST'}
/api/v1/pairing/verify {'POST'}
/api/v1/pairing/status {'GET'}
/health {'GET'}
/api/v1/health {'GET'}
```

---

### Task 5: Sync APIs

**Files:**
- Create: `D:\xm\focuspulse-server\app\schemas\sync.py`
- Create: `D:\xm\focuspulse-server\app\api\sync.py`
- Create: `D:\xm\focuspulse-server\tests\test_sync.py`
- Modify: `D:\xm\focuspulse-server\app\models\device.py` (add last_seen update helper)

**Interfaces:**
- Produces: `app.api.sync.router` — APIRouter for `/api/v1/sync/*`
- Consumes: `app.dependencies.verify_api_key` (all endpoints)

- [ ] **Step 1: Create app/schemas/sync.py**

```python
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
```

- [ ] **Step 2: Create app/api/sync.py**

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import verify_api_key
from app.models.window_event import WindowEvent
from app.models.session import DesktopSession
from app.models.pomodoro import PomodoroSessionCloud
from app.models.android_usage import AndroidAppUsage
from app.models.device import Device
from app.schemas.sync import (
    WindowEventBatch, SessionBatch, PomodoroBatch, AndroidUsageBatch,
    SyncResponse,
)

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


async def _update_device_seen(device_id: UUID, session: AsyncSession):
    """Touch last_seen_at for the device."""
    await session.execute(
        update(Device).where(Device.id == device_id).values(
            last_seen_at=__import__("datetime").datetime.now(__import__("zoneinfo").ZoneInfo("UTC"))
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
```

- [ ] **Step 3: Register router in app/main.py**

```python
from app.api.sync import router as sync_router
app.include_router(sync_router)
```

- [ ] **Step 4: Write and run a unit test for SyncResponse schema**

```python
# tests/test_sync_schema.py
from app.schemas.sync import SyncResponse


class TestSyncSchema:
    def test_sync_response_defaults(self):
        resp = SyncResponse(accepted=5)
        assert resp.accepted == 5
        assert resp.skipped == 0

    def test_sync_response_full(self):
        resp = SyncResponse(accepted=3, skipped=2)
        assert resp.accepted == 3
        assert resp.skipped == 2
```

Run:
```bash
cd D:\xm\focuspulse-server
.venv\Scripts\pytest tests/test_sync_schema.py -v
```

Expected: 2 PASS

---

### Task 6: Data Query APIs

**Files:**
- Create: `D:\xm\focuspulse-server\app\schemas\data.py`
- Create: `D:\xm\focuspulse-server\app\api\data.py`
- Create: `D:\xm\focuspulse-server\tests\test_data.py`
- Modify: `D:\xm\focuspulse-server\app\main.py` (register router)

**Interfaces:**
- Produces: `app.api.data.router` — APIRouter for `/api/v1/data/*`
- Consumes: `app.dependencies.verify_api_key`

- [ ] **Step 1: Create app/schemas/data.py**

```python
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
```

- [ ] **Step 2: Create app/api/data.py**

```python
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
```

- [ ] **Step 3: Register router in app/main.py**

```python
from app.api.data import router as data_router
app.include_router(data_router)
```

- [ ] **Step 4: Verify all routes registered**

```bash
cd D:\xm\focuspulse-server
.venv\Scripts\python -c "
from app.main import app
routes = [(r.path, sorted(r.methods)) for r in app.routes]
for p, m in sorted(routes):
    print(f'{p:45s} {m}')
"
```

Expected output:
```
/api/v1/data/apps                          ['GET']
/api/v1/data/overview                      ['GET']
/api/v1/data/pomodoros                     ['GET']
/api/v1/data/timeline                      ['GET']
/api/v1/data/trend                         ['GET']
/api/v1/health                             ['GET']
/api/v1/pairing/register                   ['POST']
/api/v1/pairing/status                     ['GET']
/api/v1/pairing/verify                     ['POST']
/api/v1/sync/app-usage                     ['POST']
/api/v1/sync/pomodoros                     ['POST']
/api/v1/sync/sessions                      ['POST']
/api/v1/sync/window-events                 ['POST']
/health                                    ['GET']
```

---

### Task 7: Daily Aggregation Task

**Files:**
- Create: `D:\xm\focuspulse-server\app\services\aggregation.py`
- Modify: `D:\xm\focuspulse-server\app\main.py` (add background task)

**Interfaces:**
- Produces: `app.services.aggregation.compute_daily_summary(device_code, date)` — upserts daily_summary record
- Consumes: All model classes

- [ ] **Step 1: Create app/services/aggregation.py**

```python
from datetime import date, datetime, timezone

from sqlalchemy import select, func, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.window_event import WindowEvent
from app.models.session import DesktopSession
from app.models.pomodoro import PomodoroSessionCloud
from app.models.android_usage import AndroidAppUsage
from app.models.daily_summary import DailySummary


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
                func.cast(
                    func.jsonb_extract_path_text(
                        DesktopSession.category_scores, "high"
                    ),
                    func.Integer,
                )
            ),
            func.sum(
                func.cast(
                    func.jsonb_extract_path_text(
                        DesktopSession.category_scores, "medium"
                    ),
                    func.Integer,
                )
            ),
            func.sum(
                func.cast(
                    func.jsonb_extract_path_text(
                        DesktopSession.category_scores, "low"
                    ),
                    func.Integer,
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
        except Exception:
            pass

    return computed
```

- [ ] **Step 2: Add scheduled task to app/main.py**

```python
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from logging import getLogger

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup: verify DB, start scheduler
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
    scheduler.start()
    logger.info(f"Daily aggregation scheduled for hour {settings.daily_summary_hour}:00 UTC")
    yield
    scheduler.shutdown()
    from app.database import engine
    await engine.dispose()


async def _run_daily_aggregation(target_date: date | None = None):
    """Compute daily summaries for all active codes."""
    from app.database import async_session_factory
    from app.services.aggregation import compute_all_active_codes

    if target_date is None:
        target_date = date.today()

    async with async_session_factory() as session:
        codes = await compute_all_active_codes(session, target_date)
        logger.info(f"Daily aggregation complete for {target_date}: {len(codes)} codes")
```

Also add `apscheduler` to pyproject.toml dependencies:
```toml
dependencies = [
    ...
    "apscheduler>=3.10",
]
```

- [ ] **Step 3: Verify scheduler import**

```bash
cd D:\xm\focuspulse-server
.venv\Scripts\pip install apscheduler
.venv\Scripts\python -c "from apscheduler.schedulers.asyncio import AsyncIOScheduler; print('APScheduler OK')"
```

Expected: `APScheduler OK`

---

### Task 8: Docker + Deployment Config

**Files:**
- Create: `D:\xm\focuspulse-server\Dockerfile`
- Create: `D:\xm\focuspulse-server\.dockerignore`
- Modify: `D:\xm\focuspulse-server\app\config.py` (add allow_env_fallback)

**Interfaces:**
- Produces: Docker image at `focuspulse-server:latest`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system deps (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy app
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create .dockerignore**

```
.venv/
__pycache__/
*.pyc
.git/
tests/
*.md
.idea/
```

- [ ] **Step 3: Verify Docker build**

```bash
cd D:\xm\focuspulse-server
docker build -t focuspulse-server:latest .
```

Expected: Image builds successfully.

---

### Task 9: Data Cleanup Task (retention)

**Files:**
- Create: `D:\xm\focuspulse-server\app\services\cleanup.py`
- Modify: `D:\xm\focuspulse-server\app\main.py` (add cleanup schedule)

**Interfaces:**
- Produces: Cleanup job that deletes window_events and android_app_usage older than 30 days

- [ ] **Step 1: Create app/services/cleanup.py**

```python
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
```

- [ ] **Step 2: Add cleanup schedule to lifespan in main.py**

Inside the scheduler block, add:
```python
scheduler.add_job(
    _run_cleanup,
    "cron",
    hour=3,
    minute=0,  # 3:00 UTC daily
)
```

And add the cleanup function:
```python
async def _run_cleanup():
    from app.database import async_session_factory
    from app.services.cleanup import purge_old_events

    async with async_session_factory() as session:
        result = await purge_old_events(session)
        logger.info(f"Data cleanup: {result}")
```

---

### Task 10: Error Handling Middleware + Response Envelope

**Files:**
- Create: `D:\xm\focuspulse-server\app\middleware.py`
- Modify: `D:\xm\focuspulse-server\app\main.py`

- [ ] **Step 1: Create app/middleware.py**

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class ResponseEnvelopeMiddleware(BaseHTTPMiddleware):
    """Wrap all responses in {data, error, code} envelope."""

    async def dispatch(self, request: Request, call_next):
        # Skip docs/openapi endpoints
        if request.url.path in ("/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        # Skip health check
        if request.url.path in ("/health", "/api/v1/health"):
            return await call_next(request)

        response = await call_next(request)

        if response.status_code >= 400:
            # Errors already handled by FastAPI exception handlers
            return response

        # For successful responses, wrap in envelope
        if response.headers.get("content-type", "").startswith("application/json"):
            body = await response.body()
            import json
            try:
                original = json.loads(body)
                wrapped = json.dumps({"data": original, "error": None, "code": response.status_code})
                return JSONResponse(
                    content=json.loads(wrapped),
                    status_code=response.status_code,
                    headers=dict(response.headers),
                )
            except (json.JSONDecodeError, ValueError):
                pass

        return response
```

Actually, this middleware approach is fragile. A cleaner approach is to use a custom APIRoute or response model. Let me simplify:

Use a response model mixin instead:

```python
# app/schemas/__init__.py  — add base envelope
from pydantic import BaseModel


class ApiResponse(BaseModel):
    data: dict | list | None = None
    error: str | None = None
    code: int = 200
```

Actually, for MVP let's keep it simple. The endpoints already return proper Pydantic models. The envelope can be added later as a middleware refinement. Remove this task from critical path.

- [ ] **Step 1: Add CORS middleware to main.py (needed for mobile clients)**

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 2: Add exception handler for clean error responses**

```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"data": None, "error": "Internal server error", "code": 500},
    )
```

---

## Verification

After all tasks are complete, verify end-to-end:

```bash
# 1. Run unit tests
cd D:\xm\focuspulse-server
.venv\Scripts\pytest tests/ -v --tb=short

# 2. Start server locally (needs PostgreSQL)
set DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/focuspulse
.venv\Scripts\uvicorn app.main:app --reload

# 3. Test health endpoint
curl http://localhost:8000/health

# 4. Test pairing flow
curl -X POST http://localhost:8000/api/v1/pairing/register \
  -H "Content-Type: application/json" \
  -d '{"device_name":"测试电脑","device_type":"desktop"}'

# 5. Test sync with the api_key from registration
curl -X POST http://localhost:8000/api/v1/sync/window-events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <api_key>" \
  -d '{"events":[{"ts":"2026-06-18T14:00:00+08:00","process":"Code.exe","category":"high","duration_seconds":120}]}'

# 6. Test query
curl -X GET "http://localhost:8000/api/v1/data/overview?device_code=<code>&date=2026-06-18" \
  -H "Authorization: Bearer <api_key>"

# 7. Build Docker image
docker build -t focuspulse-server:latest .
```
