"""
ArmorIQ SDK integration service.
Uses the official armoriq-sdk package for plan capture, token generation, and secure MCP execution.
"""
import logging
from importlib import metadata as importlib_metadata
from typing import Optional, Any, List
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings, Timeouts

# Import ArmorIQ SDK
from armoriq_sdk import ArmorIQClient
from armoriq_sdk.models import PlanCapture, IntentToken, MCPInvocationResult
from armoriq_sdk.exceptions import (
    TokenExpiredException,
    InvalidTokenException,
    IntentMismatchException,
    MCPInvocationException,
    ConfigurationException,
)

logger = logging.getLogger(__name__)
TESTED_ARMORIQ_SDK_VERSION = "0.2.6"


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a semantic version into comparable numeric parts."""
    parts: list[int] = []
    for raw_part in version_str.split("."):
        numeric = ""
        for char in raw_part:
            if char.isdigit():
                numeric += char
            else:
                break
        if not numeric:
            break
        parts.append(int(numeric))
    return tuple(parts)


# Keep these models for backward compatibility with agent_graph.py
class PlanStep(BaseModel):
    """Single step in an agent plan."""
    action: str
    mcp: str
    description: Optional[str] = None
    params: Optional[dict] = None


class AgentPlan(BaseModel):
    """Agent's execution plan."""
    steps: List[PlanStep]
    reasoning: Optional[str] = None


class ArmorIQService:
    """
    Integration layer for ArmorIQ SDK.

    Uses the official armoriq-sdk package for:
    - Plan capture before tool execution
    - Cryptographic token generation for verified execution
    - Secure MCP invocation through ArmorIQ proxy
    """

    _sdk_version_checked = False

    def __init__(self, user_id: str, agent_id: str = "chat_agent_v1"):
        """
        Initialize ArmorIQ service.

        Args:
            user_id: Current user's ID
            agent_id: Agent identifier for ArmorIQ
        """
        self.user_id = user_id
        self.agent_id = agent_id
        self._current_token: Optional[IntentToken] = None
        self._client: Optional[ArmorIQClient] = None
        self._log_sdk_version_compatibility_once()

        # Initialize ArmorIQ client if API key is available
        if settings.armoriq_api_key:
            try:
                api_key = settings.armoriq_api_key.get_secret_value()
                self._client = ArmorIQClient(
                    api_key=api_key,
                    user_id=user_id,
                    agent_id=agent_id,
                    proxy_endpoint=settings.armoriq_proxy_url,
                    backend_endpoint=settings.armoriq_backend_url,
                )
                logger.info(f"ArmorIQ SDK client initialized for user {user_id}")
            except ConfigurationException as e:
                logger.error(f"ArmorIQ SDK configuration error: {e}")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize ArmorIQ client: {e}")
                # Re-raise to ensure we don't silently fail
                raise

    @classmethod
    def _log_sdk_version_compatibility_once(cls):
        """Log SDK compatibility details once per process."""
        if cls._sdk_version_checked:
            return
        cls._sdk_version_checked = True

        try:
            installed_version = importlib_metadata.version("armoriq-sdk")
        except importlib_metadata.PackageNotFoundError:
            logger.warning("armoriq-sdk package metadata not found; skipping version compatibility check")
            return

        if _parse_version(installed_version) < _parse_version(TESTED_ARMORIQ_SDK_VERSION):
            logger.warning(
                "Installed armoriq-sdk (%s) is older than tested baseline (%s). "
                "Multi-step or multi-MCP proof validation behavior may be inconsistent.",
                installed_version,
                TESTED_ARMORIQ_SDK_VERSION,
            )
            return

        logger.info(
            "armoriq-sdk version %s meets tested baseline %s",
            installed_version,
            TESTED_ARMORIQ_SDK_VERSION,
        )

    @property
    def client(self) -> ArmorIQClient:
        """Get the ArmorIQ client, raising if not initialized."""
        if self._client is None:
            raise ConfigurationException(
                "ArmorIQ client not initialized. Check ARMORIQ_API_KEY environment variable."
            )
        return self._client

    @property
    def current_token(self) -> Optional[IntentToken]:
        """Get the current intent token."""
        return self._current_token

    @staticmethod
    def extract_result_payload(invocation_result: Any) -> Any:
        """
        Extract SDK invocation payload in a forward-compatible way.

        Canonical field is `MCPInvocationResult.result`; fallback to legacy `.data`
        if present.
        """
        if hasattr(invocation_result, "result"):
            return invocation_result.result
        if hasattr(invocation_result, "data"):
            return invocation_result.data
        return invocation_result

    def capture_plan(
        self,
        llm: str,
        prompt: str,
        plan: AgentPlan,
    ) -> PlanCapture:
        """
        Capture the plan generated by the agent.

        This is called BEFORE tool execution to register
        the intended actions with ArmorIQ.

        Args:
            llm: LLM model identifier (e.g., "openai/gpt-4o")
            prompt: Original user prompt
            plan: Agent's execution plan

        Returns:
            PlanCapture from ArmorIQ SDK with plan structure
        """
        # Convert plan to ArmorIQ format
        plan_structure = {
            "steps": [
                {
                    "action": step.action,
                    "mcp": step.mcp,
                    "description": step.description,
                    "params": step.params,
                }
                for step in plan.steps
            ]
        }

        # Use ArmorIQ SDK
        captured_plan = self.client.capture_plan(
            llm=llm,
            prompt=prompt,
            plan=plan_structure,
        )

        logger.info(f"Captured plan with {len(plan.steps)} steps using ArmorIQ SDK")
        return captured_plan

    def get_intent_token(
        self,
        captured_plan: PlanCapture,
        expires_in: int = Timeouts.ARMORIQ_TOKEN_EXPIRE_SECONDS,
        policy: Optional[dict] = None,
    ) -> IntentToken:
        """
        Get cryptographic token for plan execution.

        The token is required for executing MCP actions
        through ArmorIQ and ensures only planned actions
        are allowed.

        Args:
            captured_plan: Previously captured plan from capture_plan()
            expires_in: Token expiry in seconds
            policy: Additional policy constraints

        Returns:
            IntentToken from ArmorIQ SDK
        """
        token = self.client.get_intent_token(
            plan_capture=captured_plan,
            policy=policy or {"allow": ["*"], "deny": []},
            validity_seconds=expires_in,
        )

        self._current_token = token
        logger.info(f"Got intent token: id={token.token_id}, expires_in={token.time_until_expiry:.1f}s")
        return token

    def invoke(
        self,
        mcp_name: str,
        action: str,
        token: IntentToken,
        params: Optional[dict] = None,
        user_email: Optional[str] = None,
    ) -> MCPInvocationResult:
        """
        Execute an MCP action through ArmorIQ.

        ArmorIQ verifies that the action is part of the
        captured plan and the token is valid.

        Args:
            mcp_name: MCP server name
            action: Action/tool name
            token: IntentToken from get_intent_token
            params: Action parameters
            user_email: Optional user email for IAM context

        Returns:
            MCPInvocationResult from the SDK

        Raises:
            TokenExpiredException: If token has expired
            IntentMismatchException: If action not in plan
            MCPInvocationException: If MCP invocation fails
        """
        result = self.client.invoke(
            mcp=mcp_name,
            action=action,
            intent_token=token,
            params=params or {},
            user_email=user_email,
        )

        execution_time = getattr(result, "execution_time", None)
        if execution_time is None:
            logger.info(f"Invoked {mcp_name}/{action} successfully")
        else:
            logger.info(f"Invoked {mcp_name}/{action} successfully in {execution_time:.2f}s")
        return result

    async def save_intent_plan(
        self,
        db: AsyncSession,
        conversation_id: Optional[str],
        captured_plan: PlanCapture,
        token: Optional[IntentToken] = None,
    ) -> str:
        """
        Save captured plan to database for audit.

        Args:
            db: Database session
            conversation_id: Associated conversation ID
            captured_plan: The captured plan from SDK
            token: Optional intent token (for expiry tracking)

        Returns:
            Created plan ID
        """
        from app.models import IntentPlan

        # Extract plan data from PlanCapture
        plan_data = captured_plan.plan if hasattr(captured_plan, 'plan') else {}

        token_expires_at = None
        if token and hasattr(token, 'expires_at'):
            token_expires_at = datetime.fromtimestamp(token.expires_at)

        plan = IntentPlan(
            user_id=self.user_id,
            conversation_id=conversation_id,
            plan_hash=getattr(captured_plan, 'plan_hash', None),
            merkle_root=getattr(captured_plan, 'merkle_root', None),
            plan_data=plan_data,
            token_expires_at=token_expires_at,
            status="pending",
        )

        db.add(plan)
        await db.flush()
        await db.refresh(plan)

        return str(plan.id)

    async def update_plan_status(
        self,
        db: AsyncSession,
        plan_id: str,
        status: str,
        error_message: Optional[str] = None,
    ):
        """
        Update plan execution status.

        Args:
            db: Database session
            plan_id: Intent plan ID
            status: New status (pending, executing, completed, failed)
            error_message: Error details if failed
        """
        from app.models import IntentPlan

        result = await db.execute(
            select(IntentPlan).where(IntentPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()

        if plan:
            plan.status = status
            plan.error_message = error_message
            if status == "completed":
                plan.completed_at = datetime.utcnow()
            await db.flush()


# Export SDK exceptions for use in other modules
__all__ = [
    'ArmorIQService',
    'AgentPlan',
    'PlanStep',
    'PlanCapture',
    'IntentToken',
    'MCPInvocationResult',
    'TokenExpiredException',
    'InvalidTokenException',
    'IntentMismatchException',
    'MCPInvocationException',
    'ConfigurationException',
]
