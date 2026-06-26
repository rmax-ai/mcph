"""Tests for assertion engine behavior."""

from __future__ import annotations

from typing import Any

import pytest

from mcph.assertion import AssertionEngine, AssertionError
from mcph.ast import Assert, FuzzyType, TemplateString


def _assertion(query: str, predicate: str, expected_value: Any) -> Assert:
    return Assert(line_number=1, query=query, predicate=predicate, expected_value=expected_value)


def _success_response() -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2025-03-26",
            "serverInfo": {
                "name": "expected",
                "version": "1.2.3",
            },
            "capabilities": {
                "tools": {
                    "listChanged": True,
                }
            },
            "tools": [
                {"name": "run_sql", "inputSchema": {"type": "object"}},
                {"name": "other", "inputSchema": {"type": "object"}},
            ],
            "content": {
                "text": "critical message from server",
                "type": "text",
                "templated": "hello {{name}}",
            },
            "metrics": {
                "latencyMs": 123,
            },
            "messages": [
                {
                    "role": "assistant",
                    "content": {"text": "hello world"},
                }
            ],
            "isError": False,
            "optionalText": "present",
        },
    }


def _error_response() -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {
            "code": -32602,
            "message": "Invalid params",
        },
    }


def test_status_200() -> None:
    engine = AssertionEngine()
    assert engine.evaluate(_assertion("STATUS", "==", 200), _success_response()) is True


def test_status_error_code() -> None:
    engine = AssertionEngine()
    assert engine.evaluate(_assertion("STATUS", "==", -32602), _error_response()) is True


def test_equality_string() -> None:
    engine = AssertionEngine()
    assert (
        engine.evaluate(_assertion("serverInfo.name", "==", "expected"), _success_response())
        is True
    )


def test_equality_int() -> None:
    engine = AssertionEngine()
    assert engine.evaluate(_assertion("id", "==", 1), _success_response()) is True


def test_contains() -> None:
    engine = AssertionEngine()
    assert (
        engine.evaluate(
            _assertion("result.content.text", "CONTAINS", "critical"),
            _success_response(),
        )
        is True
    )


def test_matches_regex() -> None:
    engine = AssertionEngine()
    assert (
        engine.evaluate(
            _assertion("serverInfo.version", "MATCHES", r"^\d+\.\d+\.\d+$"),
            _success_response(),
        )
        is True
    )


def test_exists() -> None:
    engine = AssertionEngine()
    assert (
        engine.evaluate(
            _assertion("tools[*]", "EXISTS", 'name == "run_sql"'),
            _success_response(),
        )
        is True
    )


def test_count() -> None:
    engine = AssertionEngine()
    assert engine.evaluate(_assertion("tools[*]", "COUNT", ">= 1"), _success_response()) is True


def test_fuzzy_string() -> None:
    engine = AssertionEngine()
    assert engine.evaluate(
        _assertion("serverInfo.name", "==", FuzzyType(type_name="string")),
        _success_response(),
    )


def test_fuzzy_optional() -> None:
    engine = AssertionEngine()
    assertion = _assertion(
        "optionalText",
        "==",
        FuzzyType(type_name="string", optional=True),
    )

    response_with_optional = _success_response()
    response_without_optional = _success_response()
    del response_without_optional["result"]["optionalText"]

    assert engine.evaluate(assertion, response_with_optional) is True
    assert engine.evaluate(assertion, response_without_optional) is True


def test_fuzzy_wrong_type() -> None:
    engine = AssertionEngine()
    with pytest.raises(AssertionError):
        engine.evaluate(
            _assertion("id", "==", FuzzyType(type_name="string")),
            _success_response(),
        )


def test_structural_equality_dict() -> None:
    engine = AssertionEngine()
    assert engine.evaluate(
        _assertion("serverInfo", "==", {"name": "expected"}),
        _success_response(),
    )


def test_inequality() -> None:
    engine = AssertionEngine()
    assert engine.evaluate(_assertion("id", "!=", 2), _success_response()) is True


def test_numeric_greater_than() -> None:
    engine = AssertionEngine()
    assert (
        engine.evaluate(
            _assertion("result.metrics.latencyMs", ">", 100),
            _success_response(),
        )
        is True
    )


def test_assertion_error_message() -> None:
    engine = AssertionEngine()
    assertion = _assertion("tools[*]", "EXISTS", 'name == "missing"')

    with pytest.raises(AssertionError) as exc:
        engine.evaluate(assertion, _success_response())

    message = str(exc.value)
    assert message.startswith('ASSERT tools[*] EXISTS name == "missing": FAILED')
    assert "Expected:" in message
    assert "Actual:" in message


def test_jsonpath_nested() -> None:
    engine = AssertionEngine()
    assert engine.evaluate(
        _assertion("capabilities.tools.listChanged", "==", True),
        _success_response(),
    )


def test_template_string_equality() -> None:
    engine = AssertionEngine()
    assert (
        engine.evaluate(
            _assertion(
                "result.content.templated",
                "==",
                TemplateString(parts=["hello ", ("var", "name")]),
            ),
            _success_response(),
        )
        is True
    )
