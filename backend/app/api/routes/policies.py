"""
Policy management routes.

GET    /policies          — list policies for current user
POST   /policies          — create a policy
PUT    /policies/{id}     — update a policy
DELETE /policies/{id}     — delete a policy
"""
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUserId, DbSession
from app.models import PolicyCreate, PolicyUpdate
from app.models.database import Policy

router = APIRouter(prefix="/policies", tags=["Policies"])


def _row_to_dict(p: Policy) -> dict:
    return {
        "policyId": str(p.id),
        "name": p.name,
        "description": p.description,
        "targetType": p.target or "",
        "defaultEnforcementAction": p.effect,
        "isActive": p.enabled,
        "createdAt": p.created_at.isoformat(),
        "updatedAt": (p.updated_at or p.created_at).isoformat(),
    }


@router.get("")
async def list_policies(user_id: CurrentUserId, db: DbSession):
    result = await db.execute(
        select(Policy).where(Policy.user_id == user_id).order_by(Policy.created_at.desc())
    )
    return [_row_to_dict(p) for p in result.scalars().all()]


@router.post("", status_code=status.HTTP_200_OK)
async def create_policy(body: PolicyCreate, user_id: CurrentUserId, db: DbSession):
    policy = Policy(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        name=body.name,
        description=body.description,
        effect=body.resolved_effect(),
        target=body.resolved_target(),
        tools=body.tools,
        enabled=True,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return _row_to_dict(policy)


@router.put("/{policy_id}", status_code=status.HTTP_200_OK)
async def update_policy(policy_id: str, body: PolicyUpdate, user_id: CurrentUserId, db: DbSession):
    try:
        pid = uuid.UUID(policy_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid policy ID")

    result = await db.execute(select(Policy).where(Policy.id == pid, Policy.user_id == uuid.UUID(user_id)))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")

    if body.name is not None:
        policy.name = body.name
    if body.description is not None:
        policy.description = body.description
    resolved_effect = body.resolved_effect()
    if resolved_effect is not None:
        policy.effect = resolved_effect
    resolved_target = body.targetId or body.target
    if resolved_target is not None:
        policy.target = resolved_target
    if body.tools is not None:
        policy.tools = body.tools
    resolved_enabled = body.resolved_enabled()
    if resolved_enabled is not None:
        policy.enabled = resolved_enabled

    await db.commit()
    await db.refresh(policy)
    return _row_to_dict(policy)


@router.delete("/{policy_id}", status_code=status.HTTP_200_OK)
async def delete_policy(policy_id: str, user_id: CurrentUserId, db: DbSession):
    try:
        pid = uuid.UUID(policy_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid policy ID")

    result = await db.execute(select(Policy).where(Policy.id == pid, Policy.user_id == uuid.UUID(user_id)))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")

    await db.delete(policy)
    await db.commit()
    return {"ok": True}
