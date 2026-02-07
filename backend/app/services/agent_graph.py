"""
LangGraph Agent - Stateful agent with ArmorIQ integration.

Implements the Plan → Verify → Execute workflow:
1. LLM generates tool calls
2. ArmorIQ captures the plan BEFORE execution
3. Token is generated for verified execution
4. Tools are executed through ArmorIQ
5. Results fed back to LLM
"""
import logging
from typing import TypedDict, Annotated, Sequence, Optional, Any
import operator

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Defaults
from app.services.llm_router import LLMRouter
from app.services.mcp_manager import MCPManager, get_mcp_manager
from app.services.armoriq_service import (
    ArmorIQService,
    AgentPlan,
    PlanStep,
    IntentToken,
    TokenExpiredException,
)

logger = logging.getLogger(__name__)


# =============================================================================
# STATE DEFINITION
# =============================================================================
class AgentState(TypedDict):
    """State that persists across graph nodes."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    pending_tool_calls: Optional[list[dict]]
    armoriq_token: Optional[IntentToken]  # Now stores the IntentToken object
    captured_plan: Optional[dict]
    plan_id: Optional[str]
    user_id: str
    conversation_id: str
    llm_provider: str
    llm_model: str
    api_key: str


# =============================================================================
# AGENT GRAPH BUILDER
# =============================================================================
class AgentGraphBuilder:
    """
    Builds the LangGraph agent with ArmorIQ integration.

    Flow:
        User Message → LLM → [Tool Calls?]
                            ↓ Yes
                    Capture Plan (ArmorIQ)
                            ↓
                    Get Intent Token
                            ↓
                    Execute Tools
                            ↓
                    Feed Results to LLM
                            ↓
                    [More Tool Calls?] → Loop
                            ↓ No
                    Return Response
    """

    def __init__(
        self,
        llm_router: LLMRouter,
        mcp_manager: MCPManager,
        db: AsyncSession,
    ):
        self.llm_router = llm_router
        self.mcp_manager = mcp_manager
        self.db = db

    def build(self) -> StateGraph:
        """Build and compile the agent graph."""

        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("call_llm", self._call_llm)
        graph.add_node("capture_plan", self._capture_plan_with_armoriq)
        graph.add_node("execute_tools", self._execute_tools)

        # Define edges
        graph.set_entry_point("call_llm")

        graph.add_conditional_edges(
            "call_llm",
            self._should_continue,
            {
                "capture_plan": "capture_plan",
                "end": END,
            },
        )

        graph.add_edge("capture_plan", "execute_tools")
        graph.add_edge("execute_tools", "call_llm")  # Loop back for multi-step

        return graph.compile()

    async def _call_llm(self, state: AgentState) -> dict:
        """Call LLM with current messages and available tools."""

        # Get LLM instance
        llm = self.llm_router.get_llm(
            provider=state["llm_provider"],
            model=state["llm_model"],
            api_key=state["api_key"],
            streaming=False,  # Will handle streaming separately
        )

        # Auto-reconnect any idle/disconnected MCPs before loading tools
        await self.mcp_manager.ensure_user_connections(state["user_id"], self.db)

        # Get tools from connected MCPs
        tools = self.mcp_manager.get_langchain_tools(state["user_id"], self.db)

        # Bind tools if available
        if tools:
            llm_with_tools = llm.bind_tools(tools)
        else:
            llm_with_tools = llm

        # Build messages with system prompt
        messages = list(state["messages"])
        tool_names = [t.name for t in tools] if tools else []
        system_prompt = (
            "You are a helpful AI assistant with access to tools. "
            "When a user's request can be fulfilled by calling a tool, call it directly with the information provided. "
            "Do not ask for unnecessary confirmation or authorization before using tools."
        )
        if tool_names:
            system_prompt += f" Available tools: {', '.join(tool_names)}."
        messages = [SystemMessage(content=system_prompt)] + messages

        # Call LLM
        response = await llm_with_tools.ainvoke(messages)

        # Check for tool calls
        if hasattr(response, "tool_calls") and response.tool_calls:
            logger.info(f"LLM requested {len(response.tool_calls)} tool calls")
            return {
                "messages": [response],
                "pending_tool_calls": response.tool_calls,
            }
        else:
            return {
                "messages": [response],
                "pending_tool_calls": None,
            }

    async def _capture_plan_with_armoriq(self, state: AgentState) -> dict:
        """
        CRITICAL NODE: Capture plan with ArmorIQ BEFORE execution.
        """
        tool_calls = state.get("pending_tool_calls")
        if not tool_calls:
            return {}

        # Initialize ArmorIQ service
        armoriq = ArmorIQService(
            user_id=state["user_id"],
            agent_id="chat_agent_v1",
        )

        # Convert tool calls to plan - resolve MCP URLs for proxy
        def resolve_mcp_url(tool_name: str) -> str:
            short_id = self._extract_mcp_from_tool_name(tool_name)
            stripped = self.mcp_manager.get_mcp_stripped_url_by_short_id(short_id)
            return stripped or short_id

        plan = AgentPlan(
            steps=[
                PlanStep(
                    action=self._parse_tool_name(tc.get("name", tc.get("function", {}).get("name", "")))[1],
                    mcp=resolve_mcp_url(tc.get("name", "")),
                    description=f"Execute {tc.get('name', '')}",
                    params=tc.get("args", tc.get("function", {}).get("arguments", {})),
                )
                for tc in tool_calls
            ],
            reasoning="Tool execution plan from LLM",
        )

        # Get original user prompt
        user_prompt = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                user_prompt = msg.content
                break

        # Capture with ArmorIQ
        captured_plan = armoriq.capture_plan(
            llm=f"{state['llm_provider']}/{state['llm_model']}",
            prompt=user_prompt,
            plan=plan,
        )

        # Save to database
        plan_id = await armoriq.save_intent_plan(
            db=self.db,
            conversation_id=state["conversation_id"],
            captured_plan=captured_plan,
        )

        # Get execution token (now returns IntentToken object)
        intent_token = armoriq.get_intent_token(captured_plan)

        # Update plan with token info
        await armoriq.save_intent_plan(
            db=self.db,
            conversation_id=state["conversation_id"],
            captured_plan=captured_plan,
            token=intent_token,
        )

        logger.info(f"Captured plan {plan_id} with {len(tool_calls)} steps")

        return {
            "captured_plan": {
                "plan_hash": getattr(captured_plan, 'plan_hash', None),
                "steps": getattr(captured_plan, 'plan', {}).get('steps', []),
            },
            "armoriq_token": intent_token,  # Store the IntentToken object
            "plan_id": plan_id,
        }

    async def _execute_tools(self, state: AgentState) -> dict:
        """Execute tools through ArmorIQ for verification."""

        tool_calls = state.get("pending_tool_calls")
        token = state.get("armoriq_token")
        plan_id = state.get("plan_id")

        if not tool_calls or not token:
            return {"pending_tool_calls": None}

        armoriq = ArmorIQService(
            user_id=state["user_id"],
            agent_id="chat_agent_v1",
        )

        tool_messages = []

        for tc in tool_calls:
            tool_name = tc.get("name", tc.get("function", {}).get("name", ""))
            tool_args = tc.get("args", tc.get("function", {}).get("arguments", {}))
            tool_id = tc.get("id", tool_name)

            # Parse MCP ID from tool name (format: mcp_{short_id}_{tool_name})
            short_id, actual_tool_name = self._parse_tool_name(tool_name)

            # Resolve MCP identifier for proxy (expects stripped URL without protocol)
            mcp_conn = self.mcp_manager.get_mcp_by_short_id(short_id)
            if not mcp_conn:
                logger.error(f"Could not find MCP connection for short_id: {short_id}")
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: MCP not found for tool {tool_name}",
                        tool_call_id=tool_id,
                    )
                )
                continue

            # Use cached stripped URL - proxy expects bare URL without protocol
            mcp_name = self.mcp_manager.get_mcp_stripped_url_by_short_id(short_id) or mcp_conn.cached_name

            try:
                # Execute through ArmorIQ (token is now IntentToken object)
                result = armoriq.invoke(
                    mcp_name=mcp_name,  # Use stripped URL, not display name
                    action=actual_tool_name,
                    token=token,
                    params=tool_args if isinstance(tool_args, dict) else {},
                )

                # MCPInvocationResult has .result attribute
                tool_messages.append(
                    ToolMessage(
                        content=str(result.result),
                        tool_call_id=tool_id,
                    )
                )

            except Exception as e:
                import traceback
                logger.error(f"Tool execution failed: {e}\n{traceback.format_exc()}")
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: {str(e)}",
                        tool_call_id=tool_id,
                    )
                )

        # Update plan status
        if plan_id:
            all_success = all(
                "Error:" not in msg.content for msg in tool_messages
            )
            await armoriq.update_plan_status(
                db=self.db,
                plan_id=plan_id,
                status="completed" if all_success else "failed",
            )

        return {
            "messages": tool_messages,
            "pending_tool_calls": None,
            "armoriq_token": None,
        }

    def _should_continue(self, state: AgentState) -> str:
        """Decide next step based on pending tool calls."""
        if state.get("pending_tool_calls"):
            return "capture_plan"
        return "end"

    def _extract_mcp_from_tool_name(self, tool_name: str) -> str:
        """Extract MCP short_id from prefixed tool name.

        Tool names follow format: mcp_{short_id}_{tool_name}
        Example: mcp_af3abb97_wire_transfer -> af3abb97
        """
        if tool_name.startswith("mcp_"):
            rest = tool_name[4:]
            parts = rest.split("_", 1)
            if len(parts) >= 1 and len(parts[0]) == 8:
                return parts[0]
        return "default"

    def _parse_tool_name(self, tool_name: str) -> tuple[str, str]:
        """Parse MCP short_id and actual tool name from prefixed name.

        Tool names follow format: mcp_{short_id}_{tool_name}
        Example: mcp_af3abb97_wire_transfer -> (af3abb97, wire_transfer)
        """
        if tool_name.startswith("mcp_"):
            rest = tool_name[4:]
            parts = rest.split("_", 1)
            if len(parts) >= 2 and len(parts[0]) == 8:
                return parts[0], parts[1]
            logger.warning(
                f"Malformed MCP tool name '{tool_name}': expected format 'mcp_{{8-char-id}}_{{tool_name}}', falling back to 'default'"
            )
        return "default", tool_name


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================
async def run_agent(
    user_id: str,
    conversation_id: str,
    messages: list[BaseMessage],
    llm_provider: str,
    llm_model: str,
    api_key: str,
    db: AsyncSession,
) -> list[BaseMessage]:
    """
    Run the agent with the given messages.

    Args:
        user_id: Current user ID
        conversation_id: Conversation ID
        messages: Conversation messages
        llm_provider: LLM provider (e.g., "openai")
        llm_model: Model name (e.g., "gpt-4o")
        api_key: Provider API key
        db: Database session

    Returns:
        New messages generated by the agent
    """
    builder = AgentGraphBuilder(
        llm_router=LLMRouter(),
        mcp_manager=get_mcp_manager(),
        db=db,
    )

    graph = builder.build()

    initial_state: AgentState = {
        "messages": messages,
        "pending_tool_calls": None,
        "armoriq_token": None,
        "captured_plan": None,
        "plan_id": None,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "api_key": api_key,
    }

    result = await graph.ainvoke(initial_state)

    # Return only new messages (after initial ones)
    return result["messages"][len(messages):]
