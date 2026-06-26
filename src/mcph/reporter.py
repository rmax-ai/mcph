"""Reporters for rendering and persisting session results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from mcph import __version__
from mcph.ast import (
    Assert,
    ASTNode,
    CallTool,
    Capture,
    Connect,
    GetPrompt,
    Header,
    Initialize,
    Listen,
    ListPrompts,
    ListResources,
    ListTools,
    ReadResource,
    RequireCapability,
    SetVar,
    Shutdown,
    Subscribe,
)
from mcph.session import StepResult


def _is_skipped(result: StepResult) -> bool:
    return result.message.startswith("Skipped due to missing capability")


def _duration_ms(duration_ms: float) -> int:
    return round(duration_ms)


def _summary(results: list[StepResult]) -> dict[str, int]:
    skipped = sum(1 for result in results if _is_skipped(result))
    failed = sum(1 for result in results if not result.passed)
    passed = len(results) - failed - skipped
    duration = _duration_ms(sum(result.duration_ms for result in results))
    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "duration_ms": duration,
    }


def _format_expected(value: Any) -> str:
    if isinstance(value, str):
        return value
    return repr(value)


def _step_keyword_and_detail(step: ASTNode) -> tuple[str, str]:
    if isinstance(step, Connect):
        return "CONNECT", f"{step.transport} {step.target}"
    if isinstance(step, Initialize):
        return "INITIALIZE", f"protocolVersion={step.protocol_version}"
    if isinstance(step, SetVar):
        return "SET", f"{step.variable} = {_format_expected(step.value)}"
    if isinstance(step, Header):
        return "HEADER", f"{step.name} = {step.value}"
    if isinstance(step, ListTools):
        return "LIST", "tools"
    if isinstance(step, ListPrompts):
        return "LIST", "prompts"
    if isinstance(step, ListResources):
        return "LIST", "resources"
    if isinstance(step, CallTool):
        return "CALL", step.name
    if isinstance(step, ReadResource):
        return "READ", step.uri
    if isinstance(step, GetPrompt):
        return "GET", f"prompt {step.name}"
    if isinstance(step, Subscribe):
        return "SUBSCRIBE", step.uri
    if isinstance(step, Listen):
        return "LISTEN", f"{step.notification} TIMEOUT {step.timeout_ms}"
    if isinstance(step, Shutdown):
        return "SHUTDOWN", ""
    if isinstance(step, RequireCapability):
        return "REQUIRE_CAPABILITY", step.capability
    if isinstance(step, Assert):
        return "ASSERT", f"{step.query} {step.predicate} {_format_expected(step.expected_value)}"
    if isinstance(step, Capture):
        detail = f"{step.variable}: {step.query}"
        if step.regex_pattern is not None:
            regex_group = step.regex_group if step.regex_group is not None else 0
            detail = f"{detail} regex /{step.regex_pattern}/ {regex_group}"
        return "CAPTURE", detail
    return type(step).__name__.upper(), ""


def _step_name(step: ASTNode) -> str:
    keyword, detail = _step_keyword_and_detail(step)
    if detail:
        return f"{keyword} {detail}"
    return keyword


class ConsoleReporter:
    """Prints ✓/✗ per step with timing to stdout."""

    def __init__(self, file_name: str = "conformance.mcph") -> None:
        self._file_name = file_name

    def report(self, results: list[StepResult]) -> str:
        summary = _summary(results)
        width = 38
        lines = [
            f"mcph v{__version__} — {self._file_name}",
            "─" * width,
        ]

        for result in results:
            if _is_skipped(result):
                status = "○"
            elif result.passed:
                status = "✓"
            else:
                status = "✗"

            name = _step_name(result.step)
            duration = _duration_ms(result.duration_ms)
            lines.append(f"  {status} {name:<40} ({duration}ms)")
            if not result.passed:
                lines.append(f"    {result.message}")

        lines.append("─" * width)
        lines.append(
            f"{summary['passed']} passed, {summary['failed']} failed, "
            f"{summary['skipped']} skipped ({summary['duration_ms']}ms)"
        )
        return "\n".join(lines)


class JUnitReporter:
    """Produces JUnit XML string."""

    def report(self, results: list[StepResult], suite_name: str = "mcph") -> str:
        summary = _summary(results)
        total_seconds = summary["duration_ms"] / 1000
        suite = ET.Element(
            "testsuite",
            {
                "name": suite_name,
                "tests": str(len(results)),
                "failures": str(summary["failed"]),
                "time": f"{total_seconds:.3f}",
            },
        )

        for result in results:
            testcase = ET.SubElement(
                suite,
                "testcase",
                {
                    "name": _step_name(result.step),
                    "time": f"{(result.duration_ms / 1000):.3f}",
                },
            )
            if _is_skipped(result):
                skipped = ET.SubElement(testcase, "skipped")
                skipped.set("message", result.message)
            elif not result.passed:
                failure = ET.SubElement(testcase, "failure")
                failure.set("message", result.message)

        return ET.tostring(suite, encoding="unicode")


class JsonReporter:
    """Produces structured JSON string."""

    def __init__(self, file_name: str = "conformance.mcph") -> None:
        self._file_name = file_name

    def report(self, results: list[StepResult]) -> str:
        summary = _summary(results)
        steps: list[dict[str, Any]] = []

        for result in results:
            keyword, detail = _step_keyword_and_detail(result.step)
            item: dict[str, Any] = {
                "step": keyword,
                "detail": detail,
                "passed": result.passed,
                "duration_ms": _duration_ms(result.duration_ms),
            }
            if not result.passed:
                item["error"] = result.message
            steps.append(item)

        payload = {
            "version": __version__,
            "file": self._file_name,
            "summary": summary,
            "steps": steps,
        }
        return json.dumps(payload, indent=2)


def write_reports(results: list[StepResult], reporters: list[str], output_dir: str = ".") -> None:
    """Write reports to files: mcph-report.junit.xml, mcph-report.json, console output."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for reporter in reporters:
        normalized = reporter.lower()
        if normalized == "console":
            print(ConsoleReporter().report(results))
        elif normalized == "junit":
            junit_output = JUnitReporter().report(results)
            (output_path / "mcph-report.junit.xml").write_text(junit_output, encoding="utf-8")
        elif normalized == "json":
            json_output = JsonReporter().report(results)
            (output_path / "mcph-report.json").write_text(json_output, encoding="utf-8")
        else:
            raise ValueError(f"Unknown reporter '{reporter}'")
