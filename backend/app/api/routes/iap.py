"""
IAP (Intent Authorization Protocol) routes.

Handles:
  POST /iap/sdk/token     — issue an intent JWT for a captured plan
  POST /iap/verify-step   — verify a tool execution step against the token
  POST /iap/audit         — ingest a single audit log entry from the plugin
  POST /iap/audit/batch   — ingest multiple audit entries in one round-trip
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import select, func

from app.api.deps import DbSession
from app.config import settings
from app.models import (
    AuditLogCreate,
    AuditLogResponse,
    AuditBatchCreate,
    AuditBatchResponse,
    SdkTokenCreate,
    SdkTokenResponse,
    VerifyStepCreate,
)
from app.models.database import ApiKey, AuditLog, IntentPlan

router = APIRouter(prefix="/iap", tags=["IAP"])

# Token pricing (per 1M tokens, USD) — claude-sonnet-4-6 rates
_PRICE_INPUT = 3.00
_PRICE_OUTPUT = 15.00

# Rough per-tool token estimates (input, output)
_TOKEN_ESTIMATES: dict[str, tuple[int, int]] = {
    "read":      (800, 1200),
    "bash":      (600, 400),
    "edit":      (1200, 800),
    "write":     (900, 600),
    "grep":      (400, 200),
    "glob":      (300, 150),
    "webfetch":  (2000, 1500),
    "websearch": (1500, 1000),
}

def _estimate_tokens(tool: str) -> tuple[int, int]:
    return _TOKEN_ESTIMATES.get(tool.lower(), (500, 350))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def _resolve_api_key(db: DbSession, raw_key: Optional[str]) -> Optional[ApiKey]:
    """Look up an ApiKey row by its raw key value (compare against hash)."""
    if not raw_key:
        return None
    key_hash = _sha256(raw_key)
    result = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.status == "active"))
    return result.scalar_one_or_none()


def _sign_intent_jwt(plan_id: str, user_id: Optional[str], expires_in: float) -> str:
    now = datetime.utcnow()
    payload = {
        "type": "intent",
        "plan_id": plan_id,
        "user_id": user_id or "unknown",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm)


def _decode_intent_jwt(token: str) -> Optional[dict]:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["plan_id"]},
        )
    except Exception:
        return None


async def _ingest_one(db: DbSession, dto: AuditLogCreate, api_key_obj: Optional[ApiKey]) -> AuditLog:
    """Persist one audit entry and return the saved row."""
    # Decode intent JWT to link the plan
    claims = _decode_intent_jwt(dto.token)
    plan_id_str = claims.get("plan_id") if claims else None
    user_id_str = claims.get("user_id") if claims else None

    # Resolve intent_plan FK if plan exists
    intent_plan_id = None
    if plan_id_str:
        try:
            pid = uuid.UUID(plan_id_str)
            res = await db.execute(select(IntentPlan).where(IntentPlan.id == pid))
            plan_row = res.scalar_one_or_none()
            if plan_row:
                intent_plan_id = plan_row.id
        except ValueError:
            pass

    tokens_in, tokens_out = _estimate_tokens(dto.tool)

    try:
        executed_at = datetime.fromisoformat(dto.executed_at.replace("Z", "+00:00"))
    except Exception:
        executed_at = datetime.utcnow()

    log = AuditLog(
        id=uuid.uuid4(),
        api_key_id=api_key_obj.id if api_key_obj else None,
        intent_plan_id=intent_plan_id,
        user_id=uuid.UUID(user_id_str) if user_id_str and user_id_str != "unknown" else None,
        tool=dto.tool,
        action=dto.action,
        status=dto.status,
        step_index=dto.step_index,
        duration_ms=dto.duration_ms,
        tokens_input=tokens_in,
        tokens_output=tokens_out,
        session_id=dto.token[:16] if dto.token else None,
        executed_at=executed_at,
        error_message=dto.error_message,
    )
    db.add(log)
    await db.flush()
    return log


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/sdk/token", response_model=SdkTokenResponse)
async def issue_sdk_token(
    body: SdkTokenCreate,
    db: DbSession,
    x_api_key: Optional[str] = Header(None),
):
    """
    Issue an intent JWT for a captured plan.
    Called by ArmorIQClient.getIntentToken() in the @armoriq/sdk.
    """
    api_key_obj = await _resolve_api_key(db, x_api_key)

    plan_id = str(uuid.uuid4())
    plan_hash = _sha256(plan_id)
    intent_ref = f"intent-{plan_id[:8]}"
    user_id = (api_key_obj.user_id if api_key_obj else None)
    user_id_str = str(user_id) if user_id else body.user_id or "unknown"

    # Persist the plan
    plan_data = body.plan or {}
    plan_row = IntentPlan(
        id=uuid.UUID(plan_id),
        user_id=user_id if user_id else uuid.uuid4(),
        plan_hash=plan_hash[:64],
        merkle_root=_sha256(plan_hash)[:64],
        plan_data=plan_data,
        status="active",
        token_expires_at=datetime.utcnow() + timedelta(seconds=body.expires_in),
    )
    db.add(plan_row)
    await db.flush()

    jwt_token = _sign_intent_jwt(plan_id, user_id_str, body.expires_in)

    await db.commit()

    return SdkTokenResponse(
        success=True,
        plan_id=plan_id,
        intent_reference=intent_ref,
        plan_hash=plan_hash[:64],
        merkle_root=_sha256(plan_hash)[:64],
        composite_identity=f"{body.user_id or 'claude-user'}|{body.agent_id or 'claude-code'}",
        step_proofs=[],
        jwt_token=jwt_token,
        token={"signature": plan_hash[:16], "token_id": plan_id},
        client_info={"sdk": "armoriq-agent"},
        policy_validation={"passed": True},
    )


@router.post("/verify-step")
async def verify_step(body: VerifyStepCreate, db: DbSession):
    """
    Verify a tool execution step against the issued intent JWT.
    Returns allowed=True for valid, unexpired tokens.
    """
    claims = _decode_intent_jwt(body.token)

    if not claims:
        return {
            "allowed": False,
            "reason": "invalid or expired intent token",
            "skipped": False,
        }

    # Update plan status to executing
    plan_id_str = claims.get("plan_id")
    if plan_id_str:
        try:
            res = await db.execute(select(IntentPlan).where(IntentPlan.id == uuid.UUID(plan_id_str)))
            plan_row = res.scalar_one_or_none()
            if plan_row and plan_row.status == "active":
                plan_row.status = "executing"
                await db.commit()
        except Exception:
            pass

    return {
        "allowed": True,
        "reason": "ok",
        "verification_source": "armoriq-agent",
        "skipped": False,
        "step": {
            "step_index": body.step_index or 0,
            "action": body.tool_name or "unknown",
            "params": {},
        },
        "execution_state": {
            "plan_id": claims.get("plan_id", ""),
            "intent_reference": f"intent-{claims.get('plan_id', '')[:8]}",
            "executed_steps": [],
            "current_step": body.step_index or 0,
            "total_steps": 10,
            "status": "active",
            "is_completed": False,
        },
    }


@router.post("/audit", response_model=AuditLogResponse)
async def create_audit_log(
    body: AuditLogCreate,
    db: DbSession,
    x_api_key: Optional[str] = Header(None),
):
    """Ingest a single audit entry from the ArmorClaude plugin."""
    api_key_obj = await _resolve_api_key(db, x_api_key)
    log = await _ingest_one(db, body, api_key_obj)

    # Bump api_key usage counter
    if api_key_obj:
        api_key_obj.usage_count = (api_key_obj.usage_count or 0) + 1
        api_key_obj.last_used_at = datetime.utcnow()

    # Count total logs for this plan
    count_result = await db.execute(
        select(func.count()).where(AuditLog.intent_plan_id == log.intent_plan_id)
    )
    audit_index = count_result.scalar() or 1

    await db.commit()

    return AuditLogResponse(
        audit_id=str(log.id),
        iap_audit_index=audit_index,
        iap_commitment=_sha256(str(log.id))[:16],
        iap_sync_status="logged",
    )


@router.post("/audit/batch", response_model=AuditBatchResponse)
async def create_audit_log_batch(
    body: AuditBatchCreate,
    db: DbSession,
    x_api_key: Optional[str] = Header(None),
):
    """Ingest multiple audit entries in one round-trip (daemon batch flush)."""
    api_key_obj = await _resolve_api_key(db, x_api_key)
    failures: list[str] = []
    written = 0

    for row in body.rows:
        try:
            await _ingest_one(db, row, api_key_obj)
            written += 1
        except Exception as e:
            failures.append(str(e))

    if api_key_obj and written:
        api_key_obj.usage_count = (api_key_obj.usage_count or 0) + written
        api_key_obj.last_used_at = datetime.utcnow()

    await db.commit()
    return AuditBatchResponse(written=written, failures=failures)
