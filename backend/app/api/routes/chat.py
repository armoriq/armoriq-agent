"""
Chat routes with SSE streaming.
Handles conversation management and chat with streaming support.
"""
import json
import logging
from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.config import APIRoutes, ErrorMessages, Defaults
from app.api.deps import CurrentUserId, DbSession
from app.models import (
    Conversation,
    Message,
    ChatRequest,
    ConversationResponse,
    MessageResponse,
    ChatStreamChunk,
)
from app.api.routes.llm import get_user_api_key
from app.services.llm_router import LLMRouter
from app.services.mcp_manager import get_mcp_manager
from app.services.armoriq_service import ArmorIQService, AgentPlan, PlanStep
from app.services.mcp_tool_normalizer import normalize_langchain_tool_call

logger = logging.getLogger(__name__)

router = APIRouter(prefix=APIRoutes.CHAT_PREFIX, tags=["Chat"])


# =============================================================================
# CONVERSATION MANAGEMENT
# =============================================================================
@router.get(APIRoutes.CHAT_CONVERSATIONS, response_model=list[ConversationResponse])
async def list_conversations(
    user_id: CurrentUserId,
    db: DbSession,
    limit: int = 50,
):
    """Get user's conversations, most recent first."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get(APIRoutes.CHAT_HISTORY, response_model=list[MessageResponse])
async def get_conversation_history(
    conversation_id: UUID,
    user_id: CurrentUserId,
    db: DbSession,
    limit: int = Defaults.MAX_CONVERSATION_HISTORY,
):
    """Get messages in a conversation."""
    # Verify ownership
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Get messages
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    return result.scalars().all()


@router.delete(APIRoutes.CHAT_CONVERSATION)
async def delete_conversation(
    conversation_id: UUID,
    user_id: CurrentUserId,
    db: DbSession,
):
    """Delete a conversation and all its messages."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    await db.delete(conversation)
    await db.flush()

    return {"message": "Conversation deleted"}


# =============================================================================
# CHAT WITH STREAMING
# =============================================================================
@router.post(APIRoutes.CHAT_STREAM)
async def chat_stream(
    request: ChatRequest,
    user_id: CurrentUserId,
    db: DbSession,
):
    """
    Chat with the agent using Server-Sent Events (SSE) streaming.

    Returns a streaming response with chunks for:
    - content: Text being generated
    - tool_call: Tool being invoked
    - tool_result: Result from tool
    - plan_captured: ArmorIQ plan captured
    - done: Stream complete
    - error: Error occurred
    """
    # Validate/get API key for provider
    api_key = await get_user_api_key(db, user_id, request.llm_provider)
    if not api_key and request.llm_provider != "ollama":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No API key configured for {request.llm_provider}",
        )

    # Get or create conversation
    if request.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == request.conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
    else:
        # Create new conversation
        conversation = Conversation(
            user_id=user_id,
            title=request.message[:100] if request.message else "New Chat",
        )
        db.add(conversation)
        await db.flush()

    # Save user message
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.flush()

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events."""
        try:
            # Load conversation history
            result = await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at.asc())
                .limit(Defaults.MAX_CONVERSATION_HISTORY)
            )
            messages_db = result.scalars().all()

            # Convert to LangChain messages
            messages = []
            for msg in messages_db:
                if msg.role == "user":
                    messages.append(HumanMessage(content=msg.content or ""))
                elif msg.role == "assistant":
                    messages.append(AIMessage(content=msg.content or ""))
                elif msg.role == "system":
                    messages.append(SystemMessage(content=msg.content or ""))

            # Get LLM with streaming
            llm_router = LLMRouter()
            llm = llm_router.get_llm(
                provider=request.llm_provider,
                model=request.llm_model,
                api_key=api_key or "",
                streaming=True,
            )

            # Get tools from connected MCPs
            mcp_manager = get_mcp_manager()
            tools = mcp_manager.get_langchain_tools(user_id, db)

            # Bind tools if available
            if tools:
                llm_with_tools = llm.bind_tools(tools)
                yield _format_sse({"type": "info", "content": f"Connected to {len(tools)} tools"})
            else:
                llm_with_tools = llm

            # Stream LLM response
            collected_content = ""
            tool_calls = []

            async for chunk in llm_with_tools.astream(messages):
                # Handle content chunks
                if hasattr(chunk, "content") and chunk.content:
                    collected_content += chunk.content
                    yield _format_sse({
                        "type": "content",
                        "content": chunk.content,
                    })

                # Handle tool call chunks
                if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                    for tc in chunk.tool_call_chunks:
                        tool_calls.append(tc)

            # If tool calls were made, process them
            if tool_calls:
                # Aggregate tool calls
                aggregated_tools = _aggregate_tool_calls(tool_calls)

                # Validate we actually got tools
                if not aggregated_tools:
                    logger.warning("Tool calls detected but aggregation returned empty list")
                    logger.debug(f"Raw tool_calls: {tool_calls}")

                if aggregated_tools:
                    normalized_tools = [
                        normalize_langchain_tool_call(
                            tool_name=tc["name"],
                            tool_args=tc.get("args", {}),
                            resolver=mcp_manager,
                        )
                        for tc in aggregated_tools
                    ]

                    yield _format_sse({
                        "type": "tool_call",
                        "content": f"Planning {len(normalized_tools)} actions...",
                    })

                    # Create ArmorIQ plan
                    armoriq = ArmorIQService(user_id=user_id)
                    plan = AgentPlan(
                        steps=[
                            PlanStep(
                                action=step.action,
                                mcp=step.resolved_mcp_name,
                                params=step.params,
                            )
                            for step in normalized_tools
                        ]
                    )

                    # Capture plan
                    captured = armoriq.capture_plan(
                        llm=f"{request.llm_provider}/{request.llm_model}",
                        prompt=request.message,
                        plan=plan,
                    )

                    # DB connection may have gone stale during LLM streaming + SDK init.
                    # Rollback and retry once if the flush fails.
                    try:
                        plan_id = await armoriq.save_intent_plan(
                            db=db,
                            conversation_id=str(conversation.id),
                            captured_plan=captured,
                        )
                    except Exception as db_err:
                        logger.warning(f"save_intent_plan failed ({db_err}), retrying after rollback...")
                        await db.rollback()
                        plan_id = await armoriq.save_intent_plan(
                            db=db,
                            conversation_id=str(conversation.id),
                            captured_plan=captured,
                        )

                    yield _format_sse({
                        "type": "plan_captured",
                        "plan_id": plan_id,
                    })

                    # Get token and execute tools
                    token = armoriq.get_intent_token(captured)

                    tool_results = []
                    for step in normalized_tools:
                        yield _format_sse({
                            "type": "tool_call",
                            "tool_name": step.raw_tool_name,
                        })

                        if not step.is_resolved:
                            error_message = f"Could not resolve MCP for tool {step.raw_tool_name}"
                            logger.warning(error_message)
                            tool_results.append({
                                "name": step.raw_tool_name,
                                "result": {"error": error_message},
                            })
                            yield _format_sse({
                                "type": "tool_result",
                                "result": {"error": error_message},
                            })
                            continue

                        result = armoriq.invoke(
                            mcp_name=step.resolved_mcp_name,
                            action=step.action,
                            token=token,
                            params=step.params,
                        )

                        result_data = armoriq.extract_result_payload(result)

                        logger.info(f"Tool result type: {type(result)}")
                        logger.info(f"Tool result payload type: {type(result_data)}")
                        logger.info(f"Tool result payload content: {result_data}")

                        tool_results.append({
                            "name": step.raw_tool_name,
                            "result": result_data,
                        })

                        yield _format_sse({
                            "type": "tool_result",
                            "result": result_data,
                        })

                    # Continue with tool results
                    # Format results for display - parse and prettify the JSON data
                    import json
                    results_text = "\n\n**Tool Execution Results:**\n\n"

                    for tr in tool_results:
                        tool_name = tr["name"]
                        result_data = tr["result"]

                        logger.info(f"Processing tool: {tool_name}, result_data type: {type(result_data)}")

                        # Extract the actual payload from MCPInvocationResult.result.
                        # Most MCP results return a dict with "content" containing text items.
                        actual_data = None
                        if isinstance(result_data, dict) and "content" in result_data:
                            content_list = result_data["content"]
                            if isinstance(content_list, list) and len(content_list) > 0:
                                first_item = content_list[0]
                                if isinstance(first_item, dict) and "text" in first_item:
                                    # Parse the JSON string
                                    try:
                                        actual_data = json.loads(first_item["text"])
                                    except:
                                        actual_data = first_item["text"]

                        if actual_data:
                            # Pretty print the JSON
                            if isinstance(actual_data, dict):
                                # Format financial records nicely
                                if "records" in actual_data:
                                    results_text += "### Financial Records:\n\n"
                                    for record in actual_data["records"]:
                                        rec_id = record.get("record_id", "Unknown")
                                        data = record.get("data", {})
                                        results_text += f"**{rec_id}**\n"
                                        for key, value in data.items():
                                            results_text += f"  - {key.title()}: {value}\n"
                                        results_text += "\n"
                                else:
                                    # Generic dict formatting
                                    results_text += f"```json\n{json.dumps(actual_data, indent=2)}\n```\n"
                            else:
                                results_text += f"{actual_data}\n"
                        else:
                            # Fallback to string representation
                            results_text += f"{result_data}\n"

                    collected_content += results_text

                    # Send the results as content so frontend displays it
                    yield _format_sse({
                        "type": "content",
                        "content": results_text,
                    })
                else:
                    # No valid tools found, skip tool execution
                    logger.info("No valid tool calls aggregated, skipping tool execution")

            # Save assistant message (with rollback recovery for stale DB connections)
            try:
                assistant_message = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=collected_content,
                    tool_calls=tool_calls if tool_calls else None,
                )
                db.add(assistant_message)
                await db.flush()
            except Exception as db_err:
                logger.warning(f"Saving assistant message failed ({db_err}), retrying after rollback...")
                await db.rollback()
                assistant_message = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=collected_content,
                    tool_calls=tool_calls if tool_calls else None,
                )
                db.add(assistant_message)
                await db.flush()

            # Update conversation title if first message
            try:
                messages_count = await db.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation.id)
                )
                if len(list(messages_count.scalars().all())) <= 2:
                    conversation.title = request.message[:100]
                    await db.flush()
            except Exception:
                logger.warning("Failed to update conversation title, skipping")

            yield _format_sse({
                "type": "done",
                "conversation_id": str(conversation.id),
            })

        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield _format_sse({
                "type": "error",
                "message": str(e),
            })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def _format_sse(data: dict) -> str:
    """Format data as SSE event."""
    return f"data: {json.dumps(data)}\n\n"


def _aggregate_tool_calls(chunks: list) -> list[dict]:
    """Aggregate tool call chunks into complete calls."""
    logger.info(f"Starting aggregation of {len(chunks)} chunks")
    calls = {}

    for i, chunk in enumerate(chunks):
        # Chunks are dictionaries, not objects!
        chunk_index = chunk.get("index") if isinstance(chunk, dict) else getattr(chunk, "index", None)
        chunk_name = chunk.get("name") if isinstance(chunk, dict) else getattr(chunk, "name", None)
        chunk_args = chunk.get("args") if isinstance(chunk, dict) else getattr(chunk, "args", None)

        logger.info(f"Chunk {i}: index={chunk_index}, name={chunk_name}, args={chunk_args}")

        # Handle ToolCallChunk objects/dicts from streaming
        if chunk_index is not None:
            idx = chunk_index
            if idx not in calls:
                calls[idx] = {"name": "", "args_str": "", "args": {}}

            # Aggregate name (usually only in first chunk)
            if chunk_name:
                calls[idx]["name"] = chunk_name
                logger.info(f"  → Set name for index {idx}: {chunk_name}")

            # Aggregate args - they come as incremental string chunks
            if chunk_args:
                if isinstance(chunk_args, str):
                    # Concatenate string chunks
                    calls[idx]["args_str"] += chunk_args
                    logger.info(f"  → Added args chunk to index {idx}: '{chunk_args}' (total length: {len(calls[idx]['args_str'])})")
                elif isinstance(chunk_args, dict):
                    # Already a complete dict
                    calls[idx]["args"].update(chunk_args)
                    logger.info(f"  → Updated args dict for index {idx}")

        # Handle complete tool calls
        elif chunk_name and chunk_args:
            key = chunk_name if chunk_name else str(id(chunk))
            calls[key] = {
                "name": chunk_name,
                "args": chunk_args if isinstance(chunk_args, dict) else {}
            }
            logger.info(f"  → Complete tool call: {chunk_name}")

    # Now parse the concatenated args strings
    import json
    for idx, call_data in calls.items():
        if "args_str" in call_data and call_data["args_str"]:
            logger.info(f"Parsing concatenated args for index {idx}: '{call_data['args_str']}'")
            try:
                # Parse the complete concatenated JSON string
                parsed_args = json.loads(call_data["args_str"])
                call_data["args"] = parsed_args if isinstance(parsed_args, dict) else {}
                logger.info(f"  ✓ Successfully parsed args: {call_data['args']}")
            except json.JSONDecodeError as e:
                logger.error(f"  ✗ Failed to parse concatenated args: {call_data['args_str']}")
                logger.error(f"  JSON parse error: {e}")
        # Remove the temporary args_str field
        call_data.pop("args_str", None)

    # Filter out incomplete calls (no name)
    complete_calls = [call for call in calls.values() if call.get("name")]

    logger.info(f"Aggregation result: {len(complete_calls)} complete calls from {len(calls)} indices")
    if complete_calls:
        for call in complete_calls:
            logger.info(f"  → Tool: {call.get('name')}, args keys: {list(call.get('args', {}).keys())}")
    else:
        logger.error(f"Failed to aggregate tool calls from {len(chunks)} chunks")
        if chunks and len(chunks) > 0:
            sample = chunks[0]
            logger.error(f"Sample chunk type: {type(sample)}, content: {sample}")

    return complete_calls
