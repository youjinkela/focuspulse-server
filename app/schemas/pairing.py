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
