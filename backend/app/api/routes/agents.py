"""
Agent / MCP server discovery routes.

GET /agent/agents — list registered MCP servers as agents (for policy target dropdown).
"""
from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUserId, DbSession
from app.models.database import MCPConfig

router = APIRouter(prefix="/agent", tags=["Agents"])


@router.get("/agents")
async def list_agents(user_id: CurrentUserId, db: DbSession):
    result = await db.execute(
        select(MCPConfig).where(MCPConfig.user_id == user_id, MCPConfig.enabled == True)
    )
    configs = result.scalars().all()

    agents = [
        {
            "agentId": str(cfg.id),
            "name": cfg.name,
            "url": cfg.url or f"stdio://{cfg.command}",
            "orgId": str(cfg.user_id),
            "severityLevel": "low",
            "vulnerabilityScore": 0,
            "chainAttacksDetected": 0,
            "createdAt": cfg.created_at.isoformat(),
            "metadata": {"connectionType": cfg.connection_type},
        }
        for cfg in configs
    ]

    # Always include the ArmorClaude Claude Code plugin as a known agent
    armorclaude = {
        "agentId": "claude-code",
        "name": "ArmorClaude (Claude Code)",
        "url": "local://armorclaude",
        "orgId": str(user_id),
        "severityLevel": "low",
        "vulnerabilityScore": 0,
        "chainAttacksDetected": 0,
        "createdAt": "2026-01-01T00:00:00Z",
        "metadata": {"plugin": "armorclaude", "version": "0.2.2"},
    }

    return {
        "success": True,
        "data": [armorclaude, *agents],
        "count": 1 + len(agents),
    }
