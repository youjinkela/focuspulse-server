from logging import getLogger
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import verify_api_key
from app.schemas.pairing import RegisterRequest, RegisterResponse, VerifyRequest, VerifyResponse, PairingStatus
from app.services.pairing import register_device, verify_code, get_pairing_status

logger = getLogger(__name__)
router = APIRouter(prefix="/api/v1/pairing", tags=["pairing"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(req: RegisterRequest, session: AsyncSession = Depends(get_session)):
    try:
        result = await register_device(session, req.device_name, req.device_type, req.platform)
        return result
    except Exception as e:
        logger.exception(f"Device registration failed")
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/verify", response_model=VerifyResponse)
async def verify(req: VerifyRequest, session: AsyncSession = Depends(get_session)):
    try:
        result = await verify_code(session, req.device_code, req.device_name, req.device_type, req.platform)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Device verification failed")
        raise HTTPException(status_code=500, detail="Verification failed")


@router.get("/status", response_model=PairingStatus)
async def status(
    device_code: str = Query(..., min_length=6, max_length=8),
    session: AsyncSession = Depends(get_session),
    _device_id: UUID = Depends(verify_api_key),
):
    try:
        return await get_pairing_status(session, device_code)
    except Exception as e:
        logger.exception(f"Pairing status failed")
        raise HTTPException(status_code=500, detail="Failed to retrieve pairing status")
