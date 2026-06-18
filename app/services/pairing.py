from datetime import datetime, timedelta, timezone

from sqlalchemy import select
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
