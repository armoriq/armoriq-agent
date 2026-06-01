"""
API key management routes.

GET    /api-keys              — list keys for current user
POST   /api-keys              — create a new key (returns raw key once)
DELETE /api-keys/{id}         — revoke a key
GET    /api-keys/dashboard    — usage summary
GET    /api-keys/endpoint-usage — per-endpoint stats (stub)
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func

from app.api.deps import CurrentUserId, DbSession
from app.models import ApiKeyCreate, ApiKeyResponse, ApiKeyCreatedResponse
from app.models.database import ApiKey, AuditLog, User

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _row_to_response(key: ApiKey, user_email: Optional[str] = None) -> dict:
    return {
        "apiKeyId": str(key.id),
        "name": key.name,
        "description": key.description,
        "keyPrefix": key.key_prefix,
        "status": key.status,
        "usageCount": key.usage_count or 0,
        "lastUsedAt": key.last_used_at.isoformat() if key.last_used_at else None,
        "lastUsedIp": key.last_used_ip,
        "expiresAt": key.expires_at.isoformat() if key.expires_at else None,
        "createdAt": key.created_at.isoformat(),
        "createdBy": user_email,
    }


@router.get("/dashboard")
async def api_key_dashboard(user_id: CurrentUserId, db: DbSession, timeframe: str = Query("30d")):
    keys_result = await db.execute(select(func.count()).where(ApiKey.user_id == user_id))
    active_result = await db.execute(
        select(func.count()).where(ApiKey.user_id == user_id, ApiKey.status == "active")
    )
    usage_result = await db.execute(
        select(func.sum(ApiKey.usage_count)).where(ApiKey.user_id == user_id)
    )
    return {
        "success": True,
        "data": {
            "totalKeys": keys_result.scalar() or 0,
            "activeKeys": active_result.scalar() or 0,
            "totalRequests": int(usage_result.scalar() or 0),
            "timeframe": timeframe,
        },
    }


@router.get("/endpoint-usage")
async def endpoint_usage(user_id: CurrentUserId, db: DbSession, window: str = Query("30d")):
    # Return empty — per-endpoint breakdown requires request path tracking not yet implemented
    return []


@router.get("")
async def list_api_keys(
    user_id: CurrentUserId,
    db: DbSession,
    limit: int = Query(50),
    page: int = Query(1),
):
    uid = uuid.UUID(user_id)
    offset = (page - 1) * limit

    count_result = await db.execute(select(func.count()).where(ApiKey.user_id == uid))
    total = count_result.scalar() or 0

    keys_result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == uid).order_by(ApiKey.created_at.desc()).offset(offset).limit(limit)
    )
    keys = keys_result.scalars().all()

    user_result = await db.execute(select(User).where(User.id == uid))
    user = user_result.scalar_one_or_none()
    email = user.email if user else None

    return {
        "success": True,
        "data": [_row_to_response(k, email) for k in keys],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.post("", status_code=status.HTTP_200_OK)
async def create_api_key(body: ApiKeyCreate, user_id: CurrentUserId, db: DbSession):
    uid = uuid.UUID(user_id)

    # Generate the raw key — shown to the user exactly once
    raw_key = f"ak_live_{secrets.token_hex(32)}"
    key_hash = _sha256(raw_key)
    key_prefix = raw_key[:16]

    expires_at = None
    if body.expiresAt:
        expires_at = body.expiresAt if isinstance(body.expiresAt, datetime) else datetime.fromisoformat(str(body.expiresAt))

    key_row = ApiKey(
        id=uuid.uuid4(),
        user_id=uid,
        name=body.name,
        description=body.description,
        key_hash=key_hash,
        key_prefix=key_prefix,
        status="active",
        usage_count=0,
        expires_at=expires_at,
    )
    db.add(key_row)

    user_result = await db.execute(select(User).where(User.id == uid))
    user = user_result.scalar_one_or_none()

    await db.commit()
    await db.refresh(key_row)

    resp = _row_to_response(key_row, user.email if user else None)
    resp["apiKey"] = raw_key  # only on creation
    return {"success": True, "data": resp}


@router.delete("/{key_id}", status_code=status.HTTP_200_OK)
async def delete_api_key(key_id: str, user_id: CurrentUserId, db: DbSession):
    uid = uuid.UUID(user_id)
    try:
        kid = uuid.UUID(key_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid key ID")

    result = await db.execute(select(ApiKey).where(ApiKey.id == kid, ApiKey.user_id == uid))
    key_row = result.scalar_one_or_none()

    if not key_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    await db.delete(key_row)
    await db.commit()
    return {"success": True}
