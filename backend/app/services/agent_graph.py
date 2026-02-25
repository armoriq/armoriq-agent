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
from typing import TypedDict, Annotated, Sequence, Optional
import operator

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_router import LLMRouter
from app.services.mcp_manager import MCPManager, get_mcp_manager
from app.services.mcp_tool_normalizer import normalize_langchain_tool_call_payload
from app.services.armoriq_service import (
    ArmorIQService,
    AgentPlan,
    PlanStep,
    IntentToken,
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

        # Get tools from connected MCPs
        tools = self.mcp_manager.get_langchain_tools(state["user_id"], self.db)

        # Bind tools if available
        if tools:
            llm_with_tools = llm.bind_tools(tools)
        else:
            llm_with_tools = llm

        # Call LLM
        response = await llm_with_tools.ainvoke(list(state["messages"]))

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

        normalized_tool_calls = [
            normalized
            for tc in tool_calls
            if (normalized := normalize_langchain_tool_call_payload(tc, self.mcp_manager)) is not None
        ]
        if not normalized_tool_calls:
            logger.warning("No valid tool calls found while capturing plan")
            return {"pending_tool_calls": None}

        # Initialize ArmorIQ service
        armoriq = ArmorIQService(
            user_id=state["user_id"],
            agent_id="chat_agent_v1",
        )

        # Convert tool calls to plan
        plan = AgentPlan(
            steps=[
                PlanStep(
                    action=tool_call.action,
                    mcp=tool_call.resolved_mcp_name,
                    description=f"Execute {tool_call.action}",
                    params=tool_call.params,
                )
                for tool_call in normalized_tool_calls
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

        logger.info(f"Captured plan {plan_id} with {len(normalized_tool_calls)} steps")

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
            normalized = normalize_langchain_tool_call_payload(tc, self.mcp_manager)
            if normalized is None:
                logger.error("Tool execution failed: missing tool name in payload")
                tool_messages.append(
                    ToolMessage(
                        content="Error: Tool name missing in payload",
                        tool_call_id=tc.get("id", "unknown"),
                    )
                )
                continue

            tool_id = tc.get("id", normalized.raw_tool_name)
            if not normalized.is_resolved:
                logger.error(f"Could not find MCP name for short_id: {normalized.mcp_short_id}")
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: MCP not found for tool {normalized.raw_tool_name}",
                        tool_call_id=tool_id,
                    )
                )
                continue

            try:
                # Execute through ArmorIQ (token is now IntentToken object)
                result = armoriq.invoke(
                    mcp_name=normalized.resolved_mcp_name,
                    action=normalized.action,
                    token=token,
                    params=normalized.params,
                )

                result_payload = armoriq.extract_result_payload(result)
                tool_messages.append(
                    ToolMessage(
                        content=str(result_payload),
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
