"""
MCP Manager - Manages dynamic MCP connections with multiple transport options.

Supports:
- STDIO: Local MCP servers via subprocess
- SSE: Server-Sent Events (uses MCP SDK)
- HTTP: Direct HTTP/Streamable HTTP (recommended for FastMCP)
"""
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID

import httpx
from langchain_core.tools import StructuredTool
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings, Timeouts, MCPConnectionTypes, ErrorMessages
from app.models import MCPConfig, MCPConnectionStatus

logger = logging.getLogger(__name__)


class DirectMCPClient:
    """
    Direct HTTP client for FastMCP/Streamable HTTP servers.

    Bypasses the MCP SDK's streaming layer and makes direct JSON-RPC calls.
    This is more reliable for FastMCP servers that use SSE responses.
    """

    def __init__(self, url: str, auth_token: Optional[str] = None, auth_header_name: Optional[str] = None):
        self.url = url.rstrip('/')
        self.auth_token = auth_token
        self.auth_header_name = auth_header_name  # Custom header like 'CONTEXT7_API_KEY'
        self.session_id: Optional[str] = None
        self._http_client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._http_client = httpx.AsyncClient(timeout=60.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def _get_headers(self) -> dict:
        """Get headers for requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.auth_token:
            # Use custom header name if provided, otherwise default to Authorization Bearer
            if self.auth_header_name:
                headers[self.auth_header_name] = self.auth_token
            else:
                headers["Authorization"] = f"Bearer {self.auth_token}"
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        return headers

    def _parse_sse_response(self, text: str) -> Optional[dict]:
        """Parse SSE response to extract JSON data."""
        for line in text.strip().split('\n'):
            if line.startswith('data: '):
                try:
                    return json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
        return None

    async def _send_request(self, method: str, params: Optional[dict] = None, request_id: int = 1) -> dict:
        """Send a JSON-RPC request to the MCP server."""
        if not self._http_client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": request_id,
        }
        if params:
            payload["params"] = params

        response = await self._http_client.post(
            self.url,
            json=payload,
            headers=self._get_headers(),
        )

        # Extract session ID from response headers
        if "mcp-session-id" in response.headers:
            self.session_id = response.headers["mcp-session-id"]

        # Check content type
        content_type = response.headers.get("content-type", "")

        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

        if "text/event-stream" in content_type:
            # Parse SSE response
            data = self._parse_sse_response(response.text)
            if data:
                return data
            raise Exception(f"Could not parse SSE response: {response.text}")
        else:
            # Regular JSON response
            return response.json()

    async def initialize(self) -> dict:
        """Initialize the MCP session."""
        result = await self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "armoriq-agent",
                    "version": "1.0.0"
                }
            }
        )

        # Send initialized notification
        await self._send_request("notifications/initialized", {})

        return result.get("result", {})

    async def list_tools(self) -> List[dict]:
        """Get list of available tools."""
        result = await self._send_request("tools/list", {})

        if "error" in result:
            raise Exception(f"Error listing tools: {result['error']}")

        tools = result.get("result", {}).get("tools", [])
        return tools

    async def call_tool(self, name: str, arguments: dict) -> Any:
        """Execute a tool."""
        result = await self._send_request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments
            }
        )

        if "error" in result:
            raise Exception(f"Tool call error: {result['error']}")

        return result.get("result", {})


class MCPConnection:
    """Wrapper for MCP connection with metadata."""

    def __init__(self, config: MCPConfig):
        self.config = config
        self.session: Optional[ClientSession] = None
        self.direct_client: Optional[DirectMCPClient] = None  # For HTTP connections
        self.last_used: datetime = datetime.utcnow()
        self.status: str = "disconnected"  # disconnected, connecting, connected, error
        self.tools: List[dict] = []
        self.error_message: Optional[str] = None
        self._lock = asyncio.Lock()
        self._read = None
        self._write = None
        self._context_manager = None

    def is_idle(self) -> bool:
        """Check if connection has been idle beyond timeout."""
        if self.status != "connected":
            return False
        idle_time = datetime.utcnow() - self.last_used
        return idle_time > timedelta(seconds=self.config.idle_timeout_seconds)

    def touch(self):
        """Update last used timestamp."""
        self.last_used = datetime.utcnow()

    def to_status_dict(self) -> dict:
        """Convert to status dictionary."""
        return {
            "id": str(self.config.id),
            "name": self.config.name,
            "status": self.status,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "tool_count": len(self.tools),
            "idle_timeout_seconds": self.config.idle_timeout_seconds,
            "error_message": self.error_message,
            "connection_type": self.config.connection_type,
        }


class MCPManager:
    """
    Manages MCP connections with multiple transport options:
    - STDIO: For local MCP servers
    - SSE: For remote servers using MCP SDK SSE client
    - HTTP: For FastMCP/Streamable HTTP servers (direct HTTP)
    """

    def __init__(self):
        self.connections: Dict[str, MCPConnection] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start the connection manager."""
        if self._running:
            return
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_idle_connections())
        logger.info("MCP Manager started")

    async def stop(self):
        """Stop the connection manager."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        for conn in list(self.connections.values()):
            await self._disconnect(conn)

        self.connections.clear()
        logger.info("MCP Manager stopped")

    async def _cleanup_idle_connections(self):
        """Background task to clean up idle connections."""
        while self._running:
            try:
                await asyncio.sleep(Timeouts.MCP_CLEANUP_INTERVAL_SECONDS)
                for mcp_id, conn in list(self.connections.items()):
                    if conn.is_idle():
                        logger.info(f"Disconnecting idle MCP: {conn.config.name}")
                        await self._disconnect(conn)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in MCP cleanup task: {e}")

    async def _disconnect(self, conn: MCPConnection):
        """Disconnect an MCP connection."""
        async with conn._lock:
            try:
                # Close direct client if used
                if conn.direct_client:
                    await conn.direct_client.__aexit__(None, None, None)
                    conn.direct_client = None

                # Close SDK context manager if used
                if conn._context_manager:
                    try:
                        await conn._context_manager.__aexit__(None, None, None)
                    except Exception as e:
                        logger.warning(f"Error closing context manager: {e}")
                    conn._context_manager = None

                conn._read = None
                conn._write = None
                conn.session = None
            except Exception as e:
                logger.warning(f"Error disconnecting MCP {conn.config.name}: {e}")

            conn.status = "disconnected"
            conn.error_message = None

    async def connect(self, config: MCPConfig) -> bool:
        """
        Connect to an MCP server.

        Args:
            config: MCP configuration

        Returns:
            True if connected successfully
        """
        mcp_id = str(config.id)

        if mcp_id in self.connections:
            conn = self.connections[mcp_id]
            if conn.status == "connected":
                conn.touch()
                return True

        conn = MCPConnection(config)
        self.connections[mcp_id] = conn

        async with conn._lock:
            conn.status = "connecting"
            conn.error_message = None

            try:
                if config.connection_type == MCPConnectionTypes.STDIO:
                    success = await self._connect_stdio(conn)
                elif config.connection_type == MCPConnectionTypes.SSE:
                    # Try HTTP first (more reliable for FastMCP)
                    success = await self._connect_http(conn)
                    if not success:
                        # Fallback to SSE SDK
                        success = await self._connect_sse(conn)
                elif config.connection_type == MCPConnectionTypes.HTTP:
                    # Direct HTTP connection
                    success = await self._connect_http(conn)
                else:
                    raise ValueError(f"Unsupported connection type: {config.connection_type}")

                if success:
                    conn.status = "connected"
                    conn.touch()
                    logger.info(f"Connected to MCP {config.name} with {len(conn.tools)} tools")
                    return True
                else:
                    conn.status = "error"
                    conn.error_message = "Connection failed"
                    return False

            except Exception as e:
                logger.error(f"Failed to connect to MCP {config.name}: {e}")
                conn.status = "error"
                conn.error_message = str(e)
                return False

    async def _connect_stdio(self, conn: MCPConnection) -> bool:
        """Connect via stdio (local MCP servers)."""
        if not conn.config.command:
            raise ValueError("Command is required for stdio connection")

        server_params = StdioServerParameters(
            command=conn.config.command,
            args=conn.config.args or [],
            env=conn.config.env,
        )

        cm = stdio_client(server_params)
        read, write = await cm.__aenter__()
        conn._context_manager = cm
        conn._read = read
        conn._write = write

        conn.session = ClientSession(read, write)
        await conn.session.initialize()

        # Fetch tools
        tools_response = await conn.session.list_tools()
        conn.tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema if hasattr(t, 'inputSchema') else None,
            }
            for t in tools_response.tools
        ]

        return True

    async def _connect_http(self, conn: MCPConnection) -> bool:
        """Connect via direct HTTP (FastMCP/Streamable HTTP)."""
        if not conn.config.url:
            raise ValueError("URL is required for HTTP connection")

        logger.info(f"Attempting HTTP connection to {conn.config.url}")

        try:
            # Get auth token from config if available
            auth_token = getattr(conn.config, 'auth_token', None)
            auth_header_name = getattr(conn.config, 'auth_header_name', None)

            client = DirectMCPClient(
                conn.config.url,
                auth_token=auth_token,
                auth_header_name=auth_header_name
            )
            await client.__aenter__()

            # Initialize session
            init_result = await client.initialize()
            logger.info(f"HTTP MCP initialized: {init_result.get('serverInfo', {}).get('name', 'Unknown')}")

            # Fetch tools
            tools = await client.list_tools()
            conn.tools = [
                {
                    "name": t.get("name"),
                    "description": t.get("description"),
                    "input_schema": t.get("inputSchema"),
                }
                for t in tools
            ]

            conn.direct_client = client
            logger.info(f"HTTP connection successful with {len(conn.tools)} tools")
            return True

        except Exception as e:
            logger.warning(f"HTTP connection failed: {e}")
            return False

    async def _connect_sse(self, conn: MCPConnection) -> bool:
        """Connect via SSE using MCP SDK (fallback)."""
        if not conn.config.url:
            raise ValueError("URL is required for SSE connection")

        logger.info(f"Attempting SSE SDK connection to {conn.config.url}")

        try:
            from mcp.client.sse import sse_client

            cm = sse_client(conn.config.url)
            read, write = await cm.__aenter__()
            conn._context_manager = cm
            conn._read = read
            conn._write = write

            conn.session = ClientSession(read, write)

            # Use timeout for initialize
            await asyncio.wait_for(conn.session.initialize(), timeout=15.0)

            # Fetch tools
            tools_response = await asyncio.wait_for(conn.session.list_tools(), timeout=15.0)
            conn.tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.inputSchema if hasattr(t, 'inputSchema') else None,
                }
                for t in tools_response.tools
            ]

            logger.info(f"SSE SDK connection successful with {len(conn.tools)} tools")
            return True

        except asyncio.TimeoutError:
            logger.warning("SSE SDK connection timed out")
            return False
        except Exception as e:
            logger.warning(f"SSE SDK connection failed: {e}")
            return False

    async def ensure_connected(self, mcp_id: str, db: AsyncSession) -> bool:
        """Ensure MCP is connected, reconnect if needed."""
        conn = self.connections.get(mcp_id)

        if not conn:
            result = await db.execute(
                select(MCPConfig).where(MCPConfig.id == mcp_id)
            )
            config = result.scalar_one_or_none()
            if not config:
                return False
            return await self.connect(config)

        if conn.status != "connected":
            return await self.connect(conn.config)

        conn.touch()
        return True

    async def reconnect(self, mcp_id: str) -> bool:
        """Force reconnection to an MCP."""
        conn = self.connections.get(mcp_id)
        if conn:
            await self._disconnect(conn)
            return await self.connect(conn.config)
        return False

    def get_connection_status(self, user_id: str) -> List[dict]:
        """Get status of all MCP connections for a user."""
        return [
            conn.to_status_dict()
            for conn in self.connections.values()
            if str(conn.config.user_id) == user_id
        ]

    async def call_tool(
        self,
        mcp_id: str,
        tool_name: str,
        arguments: dict,
        db: AsyncSession,
    ) -> dict:
        """Execute a tool on an MCP server."""
        if not await self.ensure_connected(mcp_id, db):
            raise ConnectionError(f"{ErrorMessages.MCP_NOT_CONNECTED}: {mcp_id}")

        conn = self.connections[mcp_id]
        conn.touch()

        try:
            # Use direct client if available (HTTP connection)
            if conn.direct_client:
                result = await conn.direct_client.call_tool(tool_name, arguments)
                return {
                    "success": True,
                    "data": result.get("content", result),
                }
            # Use SDK session
            elif conn.session:
                result = await conn.session.call_tool(tool_name, arguments)
                return {
                    "success": True,
                    "data": result.content if hasattr(result, 'content') else result,
                }
            else:
                raise RuntimeError("No active connection")

        except Exception as e:
            logger.error(f"Tool call failed on {conn.config.name}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_mcp_by_short_id(self, short_id: str) -> Optional[MCPConnection]:
        """
        Find MCP connection by short_id prefix.

        Tool names are formatted as: mcp_{short_id}_{tool_name}
        where short_id is the first 8 chars of the UUID without hyphens.

        Args:
            short_id: The 8-character short ID prefix (e.g., 'af3abb97')

        Returns:
            MCPConnection if found, None otherwise
        """
        for mcp_id, conn in self.connections.items():
            # short_id is first 8 chars of UUID without hyphens
            mcp_short_id = mcp_id.replace('-', '')[:8]
            if mcp_short_id == short_id:
                return conn
        return None

    def get_mcp_name_by_short_id(self, short_id: str) -> Optional[str]:
        """
        Get the actual MCP name by short_id.

        Returns the registered name (e.g., 'loan-mcp') that the proxy knows about.
        """
        conn = self.get_mcp_by_short_id(short_id)
        return conn.config.name if conn else None

    def get_mcp_id_by_short_id(self, short_id: str) -> Optional[str]:
        """Get the full MCP UUID by short_id."""
        conn = self.get_mcp_by_short_id(short_id)
        return str(conn.config.id) if conn else None

    def get_tools_for_user(self, user_id: str) -> List[dict]:
        """Get all tools from connected MCPs for a user."""
        all_tools = []
        for mcp_id, conn in self.connections.items():
            if str(conn.config.user_id) != user_id:
                continue
            if not conn.config.enabled:
                continue
            if conn.status != "connected":
                continue
            for tool_def in conn.tools:
                all_tools.append({
                    "mcp_id": mcp_id,
                    "mcp_name": conn.config.name,
                    **tool_def,
                })
        return all_tools

    def get_langchain_tools(self, user_id: str, db: AsyncSession) -> List[StructuredTool]:
        """Get all tools from connected MCPs as LangChain tools."""
        all_tools = []
        for mcp_id, conn in self.connections.items():
            if str(conn.config.user_id) != user_id:
                continue
            if not conn.config.enabled:
                continue
            if conn.status != "connected":
                continue
            for tool_def in conn.tools:
                tool = self._create_langchain_tool(mcp_id, tool_def, db)
                all_tools.append(tool)
        return all_tools

    def _create_langchain_tool(
        self,
        mcp_id: str,
        tool_def: dict,
        db: AsyncSession,
    ) -> StructuredTool:
        """Convert MCP tool to LangChain StructuredTool."""
        async def tool_func(**kwargs) -> str:
            result = await self.call_tool(mcp_id, tool_def["name"], kwargs, db)
            if result.get("success"):
                return str(result.get("data", ""))
            else:
                return f"Error: {result.get('error', 'Unknown error')}"

        # Format: mcp_{short_id}_{tool_name}
        short_id = mcp_id.replace('-', '')[:8]
        unique_name = f"mcp_{short_id}_{tool_def['name']}"

        # Create args_schema from input_schema if available
        args_schema = None
        input_schema = tool_def.get("input_schema")
        if input_schema:
            try:
                from pydantic import create_model, Field
                from typing import Any, Optional

                # Build field definitions from JSON schema properties
                properties = input_schema.get("properties", {})
                required_fields = input_schema.get("required", [])

                field_definitions = {}
                for prop_name, prop_schema in properties.items():
                    prop_type = prop_schema.get("type", "string")
                    prop_desc = prop_schema.get("description", "")

                    # Map JSON schema types to Python types
                    type_mapping = {
                        "string": str,
                        "integer": int,
                        "number": float,
                        "boolean": bool,
                        "array": list,
                        "object": dict,
                    }
                    python_type = type_mapping.get(prop_type, Any)

                    # Required fields vs optional
                    if prop_name in required_fields:
                        field_definitions[prop_name] = (python_type, Field(description=prop_desc))
                    else:
                        field_definitions[prop_name] = (Optional[python_type], Field(default=None, description=prop_desc))

                if field_definitions:
                    # Create a unique model name
                    model_name = f"{unique_name.replace('-', '_')}_Args"
                    args_schema = create_model(model_name, **field_definitions)

            except Exception as e:
                logger.warning(f"Failed to create args_schema for {unique_name}: {e}")

        return StructuredTool.from_function(
            coroutine=tool_func,
            name=unique_name,
            description=tool_def.get("description", f"Tool from MCP: {tool_def['name']}"),
            args_schema=args_schema,
        )


# Singleton instance
mcp_manager = MCPManager()


def get_mcp_manager() -> MCPManager:
    """Get the MCP manager singleton."""
    return mcp_manager
