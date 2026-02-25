"""
Regression tests for multi-step MCP tool normalization identity.
"""

from __future__ import annotations

from typing import Optional

from app.services.mcp_tool_normalizer import (
    NormalizedToolCall,
    normalize_langchain_tool_call,
    normalize_langchain_tool_call_payload,
)


class _ResolverStub:
    def __init__(self, mapping: dict[str, str]):
        self._mapping = mapping

    def get_mcp_name_by_short_id(self, short_id: str) -> Optional[str]:
        return self._mapping.get(short_id)


def _step_tuple(step: NormalizedToolCall) -> tuple[str, str, dict]:
    return (step.resolved_mcp_name, step.action, step.params)


def test_multi_step_same_mcp_capture_and_execute_identity():
    resolver = _ResolverStub({"af3abb97": "finance-mcp"})
    tool_calls = [
        {"name": "mcp_af3abb97_get_balance", "args": {"account_id": "acc-1"}},
        {"name": "mcp_af3abb97_wire_transfer", "args": {"amount": 250}},
    ]

    captured_steps = [
        normalize_langchain_tool_call(tc["name"], tc["args"], resolver)
        for tc in tool_calls
    ]
    executed_steps = [
        normalize_langchain_tool_call_payload(tc, resolver)
        for tc in tool_calls
    ]

    captured_identity = [_step_tuple(step) for step in captured_steps]
    executed_identity = [_step_tuple(step) for step in executed_steps if step is not None]

    assert captured_identity == executed_identity
    assert all(step[0] == "finance-mcp" for step in captured_identity)


def test_multi_step_cross_mcp_capture_and_execute_identity():
    resolver = _ResolverStub(
        {
            "af3abb97": "finance-mcp",
            "bf2cd910": "travel-mcp",
        }
    )
    tool_calls = [
        {"name": "mcp_af3abb97_get_balance", "args": {"account_id": "acc-1"}},
        {"name": "mcp_bf2cd910_book_flight", "args": {"destination": "JFK"}},
    ]

    captured_steps = [
        normalize_langchain_tool_call(tc["name"], tc["args"], resolver)
        for tc in tool_calls
    ]
    executed_steps = [
        normalize_langchain_tool_call_payload(tc, resolver)
        for tc in tool_calls
    ]

    captured_identity = [_step_tuple(step) for step in captured_steps]
    executed_identity = [_step_tuple(step) for step in executed_steps if step is not None]

    assert captured_identity == executed_identity
    assert captured_identity[0][0] == "finance-mcp"
    assert captured_identity[1][0] == "travel-mcp"


def test_same_action_name_is_disambiguated_by_mcp():
    resolver = _ResolverStub(
        {
            "af3abb97": "finance-mcp",
            "bf2cd910": "loan-mcp",
        }
    )
    finance_call = normalize_langchain_tool_call(
        "mcp_af3abb97_get_status",
        {"entity_id": "f-1"},
        resolver,
    )
    loan_call = normalize_langchain_tool_call(
        "mcp_bf2cd910_get_status",
        {"entity_id": "l-1"},
        resolver,
    )

    assert finance_call.action == loan_call.action == "get_status"
    assert finance_call.resolved_mcp_name == "finance-mcp"
    assert loan_call.resolved_mcp_name == "loan-mcp"
    assert _step_tuple(finance_call) != _step_tuple(loan_call)


def test_string_arguments_are_normalized_to_dict():
    resolver = _ResolverStub({"af3abb97": "finance-mcp"})
    tool_call = {
        "name": "mcp_af3abb97_get_balance",
        "args": '{"account_id": "acc-1"}',
    }

    normalized = normalize_langchain_tool_call_payload(tool_call, resolver)

    assert normalized is not None
    assert normalized.params == {"account_id": "acc-1"}
    assert normalized.resolved_mcp_name == "finance-mcp"
