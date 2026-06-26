"""Variable capture registry for CAPTURE, SET, and template resolution."""

from __future__ import annotations

import re
from typing import Any

from jsonpath_ng.ext import parse as parse_jsonpath  # type: ignore[import-untyped]

from mcph.ast import Capture, TemplateString

TEMPLATE_RE = re.compile(r"\{\{(\w+(?:\.\w+)*)\}\}")
FULL_TEMPLATE_RE = re.compile(r"^\{\{(\w+(?:\.\w+)*)\}\}$")


class CaptureError(Exception):
    """Raised when a capture extraction fails."""


class CaptureRegistry:
    """Store captured variables and resolve templates against them."""

    def __init__(self) -> None:
        self._vars: dict[str, Any] = {}

    def set(self, name: str, value: Any) -> None:
        """Set a variable directly (from SET directive)."""
        self._vars[name] = value

    def capture(self, capture: Capture, response: dict[str, Any]) -> None:
        """Extract and store a value from response using JSONPath and optional regex."""
        try:
            matches = parse_jsonpath(capture.query).find(response)
        except Exception as exc:
            raise CaptureError(f"Invalid capture query '{capture.query}': {exc}") from exc

        if not matches:
            raise CaptureError(f"Capture query '{capture.query}' returned no results")

        value: Any = matches[0].value

        if capture.regex_pattern is not None:
            match = re.search(capture.regex_pattern, str(value))
            if match is None:
                raise CaptureError(
                    f"Regex '{capture.regex_pattern}' did not match value for '{capture.variable}'"
                )
            group = capture.regex_group if capture.regex_group is not None else 0
            try:
                value = match.group(group)
            except IndexError as exc:
                raise CaptureError(
                    f"Regex group {group} not found for pattern '{capture.regex_pattern}'"
                ) from exc

        self._vars[capture.variable] = value

    def resolve(self, value: Any) -> Any:
        """Recursively resolve TemplateStrings and {{var}} placeholders."""
        if isinstance(value, TemplateString):
            return self._resolve_template_string(value)
        if isinstance(value, str):
            return self._resolve_string(value)
        if isinstance(value, dict):
            return {key: self.resolve(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.resolve(item) for item in value]
        return value

    def _resolve_template_string(self, value: TemplateString) -> Any:
        if len(value.parts) == 1 and isinstance(value.parts[0], tuple):
            return self._lookup(value.parts[0][1])

        rendered: list[str] = []
        for part in value.parts:
            if isinstance(part, str):
                rendered.append(part)
            else:
                rendered.append(str(self._lookup(part[1])))
        return "".join(rendered)

    def _resolve_string(self, value: str) -> Any:
        full_match = FULL_TEMPLATE_RE.fullmatch(value)
        if full_match is not None:
            return self._lookup(full_match.group(1))

        if TEMPLATE_RE.search(value) is None:
            return value

        return TEMPLATE_RE.sub(lambda match: str(self._lookup(match.group(1))), value)

    def _lookup(self, name: str) -> Any:
        if name in self._vars:
            return self._vars[name]

        parts = name.split(".")
        root = parts[0]
        if root not in self._vars:
            raise self._missing_variable(root)

        current = self._vars[root]
        for part in parts[1:]:
            if not isinstance(current, dict) or part not in current:
                raise self._missing_variable(name)
            current = current[part]
        return current

    def _missing_variable(self, name: str) -> CaptureError:
        available = ", ".join(sorted(self._vars)) if self._vars else "<none>"
        return CaptureError(f"Variable '{name}' not found. Available variables: {available}")
