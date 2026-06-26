"""Tests for variable capture and template resolution."""

from __future__ import annotations

import pytest

from mcph.ast import Capture
from mcph.capture import CaptureError, CaptureRegistry


def test_capture_jsonpath() -> None:
    registry = CaptureRegistry()
    node = Capture(variable="x", query="result.id", line_number=1)
    response = {"result": {"id": "abc-123"}}

    registry.capture(node, response)

    assert registry.resolve("{{x}}") == "abc-123"


def test_capture_nested_jsonpath() -> None:
    registry = CaptureRegistry()
    node = Capture(variable="x", query="result.item.meta.id", line_number=1)
    response = {"result": {"item": {"meta": {"id": "nested-id"}}}}

    registry.capture(node, response)

    assert registry.resolve("{{x}}") == "nested-id"


def test_capture_regex() -> None:
    registry = CaptureRegistry()
    node = Capture(
        variable="item_id",
        query="result.text",
        regex_pattern=r"id=(\d+)",
        regex_group=1,
        line_number=1,
    )
    response = {"result": {"text": "created id=42 successfully"}}

    registry.capture(node, response)

    assert registry.resolve("{{item_id}}") == "42"


def test_capture_regex_no_match() -> None:
    registry = CaptureRegistry()
    node = Capture(
        variable="item_id",
        query="result.text",
        regex_pattern=r"id=(\d+)",
        regex_group=1,
        line_number=1,
    )
    response = {"result": {"text": "no id here"}}

    with pytest.raises(CaptureError, match="did not match"):
        registry.capture(node, response)


def test_set_variable() -> None:
    registry = CaptureRegistry()
    registry.set("_meta.protocolVersion", "value")

    assert registry.resolve("{{_meta.protocolVersion}}") == "value"


def test_resolve_simple() -> None:
    registry = CaptureRegistry()
    registry.set("x", 123)

    assert registry.resolve("{{x}}") == 123


def test_resolve_nested() -> None:
    registry = CaptureRegistry()
    registry.set("x", {"y": {"z": "deep"}})

    assert registry.resolve("{{x.y.z}}") == "deep"


def test_resolve_in_dict() -> None:
    registry = CaptureRegistry()
    registry.set("item_id", 7)
    registry.set("ref_id", "ref-9")
    payload = {"id": "{{item_id}}", "data": {"ref": "{{ref_id}}"}}

    assert registry.resolve(payload) == {"id": 7, "data": {"ref": "ref-9"}}


def test_resolve_in_list() -> None:
    registry = CaptureRegistry()
    registry.set("a", "alpha")
    registry.set("b", 2)
    payload = ["{{a}}", {"count": "{{b}}"}, "literal"]

    assert registry.resolve(payload) == ["alpha", {"count": 2}, "literal"]


def test_resolve_missing_variable() -> None:
    registry = CaptureRegistry()
    registry.set("known", "yes")

    with pytest.raises(CaptureError, match="Variable 'x' not found") as exc_info:
        registry.resolve("{{x}}")

    assert "Available variables: known" in str(exc_info.value)


def test_resolve_no_templates() -> None:
    registry = CaptureRegistry()

    assert registry.resolve("plain string") == "plain string"


def test_capture_missing_path() -> None:
    registry = CaptureRegistry()
    node = Capture(variable="x", query="result.missing.path", line_number=1)
    response = {"result": {"id": "abc-123"}}

    with pytest.raises(CaptureError, match="returned no results"):
        registry.capture(node, response)
