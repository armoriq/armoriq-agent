"""
Intent plans routes.
View and manage ArmorIQ captured plans.
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.config import APIRoutes, ErrorMessages
from app.api.deps import CurrentUserId, DbSession
from app.models import IntentPlan, IntentPlanResponse


router = APIRouter(prefix=APIRoutes.PLANS_PREFIX, tags=["Intent Plans"])


@router.get(APIRoutes.PLANS_LIST, response_model=list[IntentPlanResponse])
async def list_plans(
    user_id: CurrentUserId,
    db: DbSession,
    limit: int = 50,
    status_filter: str = None,
):
    """
    Get user's intent plans.

    Args:
        limit: Maximum number of plans to return
        status_filter: Filter by status (pending, executing, completed, failed)
    """
    query = select(IntentPlan).where(IntentPlan.user_id == user_id)

    if status_filter:
        query = query.where(IntentPlan.status == status_filter)

    query = query.order_by(IntentPlan.created_at.desc()).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router.get(APIRoutes.PLANS_DETAIL, response_model=IntentPlanResponse)
async def get_plan(
    plan_id: UUID,
    user_id: CurrentUserId,
    db: DbSession,
):
    """Get details of a specific intent plan."""
    result = await db.execute(
        select(IntentPlan).where(
            IntentPlan.id == plan_id,
            IntentPlan.user_id == user_id,
        )
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.NOT_FOUND,
        )

    return plan
