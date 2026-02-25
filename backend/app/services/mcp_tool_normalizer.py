"""
Shared MCP tool normalization helpers.

These helpers keep plan-capture and tool-execution identity consistent by
normalizing tool names and arguments in one place.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional, Protocol

DEFAULT_MCP_SHORT_ID = "default"
DEFAULT_MCP_NAME = "default-mcp"


class MCPNameResolver(Protocol):
    """Protocol for resolving MCP short IDs to actual MCP names."""

    def get_mcp_name_by_short_id(self, short_id: str) -> Optional[str]:
        """Resolve an MCP short ID to the actual MCP name."""


@dataclass(frozen=True)
class NormalizedToolCall:
    """Normalized representation of an MCP tool call."""

    raw_tool_name: str
    mcp_short_id: str
    mcp_name: Optional[str]
    action: str
    params: dict[str, Any]

    @property
    def resolved_mcp_name(self) -> str:
        """Best-effort MCP identifier for plan capture and execution."""
        if self.mcp_name:
            return self.mcp_name
        if self.mcp_short_id != DEFAULT_MCP_SHORT_ID:
            return self.mcp_short_id
        return DEFAULT_MCP_NAME

    @property
    def is_resolved(self) -> bool:
        """Whether a concrete MCP name was successfully resolved."""
        return self.mcp_name is not None


def parse_langchain_tool_name(tool_name: str) -> tuple[str, str]:
    """
    Parse MCP short ID and action from a LangChain tool name.

    Supported formats:
    - mcp_<short_id>_<action>
    - <legacy_id>__<action> (legacy fallback)
    """
    if tool_name.startswith("mcp_"):
        rest = tool_name[4:]
        short_id, separator, action = rest.partition("_")
        if separator and len(short_id) == 8 and action:
            return short_id, action

    if "__" in tool_name:
        legacy_id, action = tool_name.split("__", 1)
        if action:
            return _normalize_short_id(legacy_id), action

    return DEFAULT_MCP_SHORT_ID, tool_name


def normalize_langchain_tool_call(
    tool_name: str,
    tool_args: Any,
    resolver: MCPNameResolver,
) -> NormalizedToolCall:
    """Normalize a single tool call."""
    short_id, action = parse_langchain_tool_name(tool_name)
    params = coerce_tool_args(tool_args)

    mcp_name: Optional[str] = None
    if short_id != DEFAULT_MCP_SHORT_ID:
        mcp_name = resolver.get_mcp_name_by_short_id(short_id)

    return NormalizedToolCall(
        raw_tool_name=tool_name,
        mcp_short_id=short_id,
        mcp_name=mcp_name,
        action=action,
        params=params,
    )


def normalize_langchain_tool_call_payload(
    tool_call: dict[str, Any],
    resolver: MCPNameResolver,
) -> Optional[NormalizedToolCall]:
    """Normalize a LangChain tool-call payload dict."""
    function_data = tool_call.get("function", {})
    tool_name = tool_call.get("name", function_data.get("name", ""))
    if not tool_name:
        return None

    tool_args = tool_call.get("args", function_data.get("arguments", {}))
    return normalize_langchain_tool_call(tool_name, tool_args, resolver)


def coerce_tool_args(tool_args: Any) -> dict[str, Any]:
    """Coerce tool args to a dictionary."""
    if isinstance(tool_args, dict):
        return tool_args

    if isinstance(tool_args, str):
        try:
            parsed = json.loads(tool_args)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}

    return {}


def _normalize_short_id(value: str) -> str:
    """Normalize IDs to an 8-char compact short form when possible."""
    compact = value.replace("-", "").replace("_", "")
    if len(compact) >= 8:
        return compact[:8]
    return value


__all__ = [
    "DEFAULT_MCP_NAME",
    "DEFAULT_MCP_SHORT_ID",
    "MCPNameResolver",
    "NormalizedToolCall",
    "coerce_tool_args",
    "normalize_langchain_tool_call",
    "normalize_langchain_tool_call_payload",
    "parse_langchain_tool_name",
]
