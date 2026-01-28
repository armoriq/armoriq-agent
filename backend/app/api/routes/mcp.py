"""
MCP configuration routes.
Manages user's MCP server connections.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import APIRoutes, ErrorMessages
from app.api.deps import CurrentUserId, DbSession
from app.models import (
    MCPConfig,
    MCPConfigCreate,
    MCPConfigUpdate,
    MCPConfigResponse,
    MCPStatusResponse,
    MCPToolResponse,
)
from app.services.mcp_manager import get_mcp_manager, MCPManager


router = APIRouter(prefix=APIRoutes.MCP_PREFIX, tags=["MCP Configuration"])


def get_mcp_manager_dep() -> MCPManager:
    """Dependency to get MCP manager."""
    return get_mcp_manager()


@router.post(APIRoutes.MCP_ADD, response_model=MCPConfigResponse)
async def add_mcp(
    data: MCPConfigCreate,
    user_id: CurrentUserId,
    db: DbSession,
    mcp_manager: MCPManager = Depends(get_mcp_manager_dep),
):
    """
    Add a new MCP server configuration.

    Attempts to connect immediately to validate the configuration.
    """
    # Check for duplicate name
    result = await db.execute(
        select(MCPConfig).where(
            MCPConfig.user_id == user_id,
            MCPConfig.name == data.name,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.MCP_ALREADY_EXISTS,
        )

    # Create config in database
    config = MCPConfig(
        user_id=user_id,
        name=data.name,
        connection_type=data.connection_type,
        url=data.url,
        command=data.command,
        args=data.args,
        env=data.env,
        idle_timeout_seconds=data.idle_timeout_seconds,
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)

    # Try to connect
    success = await mcp_manager.connect(config)

    if not success:
        # Connection failed, but config is saved
        # User can try reconnecting later
        pass

    return config


@router.get(APIRoutes.MCP_LIST, response_model=list[MCPConfigResponse])
async def list_mcps(
    user_id: CurrentUserId,
    db: DbSession,
):
    """Get all MCP configurations for current user."""
    result = await db.execute(
        select(MCPConfig)
        .where(MCPConfig.user_id == user_id)
        .order_by(MCPConfig.created_at.desc())
    )
    return result.scalars().all()


@router.get(APIRoutes.MCP_STATUS, response_model=list[MCPStatusResponse])
async def get_mcp_status(
    user_id: CurrentUserId,
    db: DbSession,
    mcp_manager: MCPManager = Depends(get_mcp_manager_dep),
):
    """
    Get connection status of all MCPs.

    Returns current connection state, tool count, and any errors.
    """
    # Get all user's configs
    result = await db.execute(
        select(MCPConfig).where(MCPConfig.user_id == user_id)
    )
    configs = result.scalars().all()

    statuses = []
    for config in configs:
        mcp_id = str(config.id)
        conn = mcp_manager.connections.get(mcp_id)

        if conn:
            statuses.append(MCPStatusResponse(
                id=config.id,
                name=config.name,
                status=conn.status,
                last_used=conn.last_used,
                tool_count=len(conn.tools),
                idle_timeout_seconds=config.idle_timeout_seconds,
                error_message=conn.error_message,
            ))
        else:
            statuses.append(MCPStatusResponse(
                id=config.id,
                name=config.name,
                status="disconnected",
                last_used=None,
                tool_count=0,
                idle_timeout_seconds=config.idle_timeout_seconds,
            ))

    return statuses


@router.post(APIRoutes.MCP_RECONNECT)
async def reconnect_mcp(
    mcp_id: UUID,
    user_id: CurrentUserId,
    db: DbSession,
    mcp_manager: MCPManager = Depends(get_mcp_manager_dep),
):
    """
    Reconnect to a specific MCP server.

    Useful after idle timeout or connection errors.
    """
    # Verify ownership
    result = await db.execute(
        select(MCPConfig).where(
            MCPConfig.id == mcp_id,
            MCPConfig.user_id == user_id,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.MCP_NOT_FOUND,
        )

    # Reconnect
    success = await mcp_manager.connect(config)

    conn = mcp_manager.connections.get(str(mcp_id))

    return {
        "status": "connected" if success else "error",
        "tool_count": len(conn.tools) if conn else 0,
        "error_message": conn.error_message if conn else None,
    }


@router.get(APIRoutes.MCP_TOOLS)
async def get_mcp_tools(
    mcp_id: UUID,
    user_id: CurrentUserId,
    db: DbSession,
    mcp_manager: MCPManager = Depends(get_mcp_manager_dep),
):
    """
    Get tools available from a specific MCP.

    Attempts to connect if not already connected.
    """
    # Verify ownership
    result = await db.execute(
        select(MCPConfig).where(
            MCPConfig.id == mcp_id,
            MCPConfig.user_id == user_id,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.MCP_NOT_FOUND,
        )

    # Ensure connected
    mcp_id_str = str(mcp_id)
    if not await mcp_manager.ensure_connected(mcp_id_str, db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorMessages.MCP_CONNECTION_FAILED,
        )

    conn = mcp_manager.connections.get(mcp_id_str)
    return {"tools": conn.tools if conn else []}


@router.patch(APIRoutes.MCP_UPDATE_TIMEOUT)
async def update_idle_timeout(
    mcp_id: UUID,
    timeout_seconds: int,
    user_id: CurrentUserId,
    db: DbSession,
):
    """
    Update idle timeout for an MCP connection.

    Args:
        timeout_seconds: New timeout in seconds (minimum 60)
    """
    if timeout_seconds < 60:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Timeout must be at least 60 seconds",
        )

    # Verify ownership and update
    result = await db.execute(
        select(MCPConfig).where(
            MCPConfig.id == mcp_id,
            MCPConfig.user_id == user_id,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.MCP_NOT_FOUND,
        )

    config.idle_timeout_seconds = timeout_seconds
    await db.flush()

    return {"status": "updated", "idle_timeout_seconds": timeout_seconds}


@router.delete(APIRoutes.MCP_DELETE)
async def delete_mcp(
    mcp_id: UUID,
    user_id: CurrentUserId,
    db: DbSession,
    mcp_manager: MCPManager = Depends(get_mcp_manager_dep),
):
    """
    Delete an MCP configuration.

    Disconnects if currently connected.
    """
    # Verify ownership
    result = await db.execute(
        select(MCPConfig).where(
            MCPConfig.id == mcp_id,
            MCPConfig.user_id == user_id,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.MCP_NOT_FOUND,
        )

    # Disconnect if connected
    mcp_id_str = str(mcp_id)
    if mcp_id_str in mcp_manager.connections:
        conn = mcp_manager.connections[mcp_id_str]
        await mcp_manager._disconnect(conn)
        del mcp_manager.connections[mcp_id_str]

    # Delete from database
    await db.delete(config)
    await db.flush()

    return {"message": "MCP deleted"}
