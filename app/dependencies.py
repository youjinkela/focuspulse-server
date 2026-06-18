from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import hash_api_key
from app.config import generate_api_key  # re-exported: app.dependencies.hash_api_key / generate_api_key
from app.database import get_session
from app.models.device import Device

# Re-exported for convenience
hash_api_key = hash_api_key
generate_api_key = generate_api_key


async def verify_api_key(
    authorization: str = Header(..., description="Bearer <api_key>"),
    session: AsyncSession = Depends(get_session),
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
