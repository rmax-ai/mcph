"""Tests for mcph.reporter."""

from __future__ import annotations

import json
from xml.etree import ElementTree as ET

from mcph.ast import Assert, Connect, Initialize, ListTools, Shutdown
from mcph.reporter import ConsoleReporter, JsonReporter, JUnitReporter, write_reports
from mcph.session import StepResult


def _sample_results() -> list[StepResult]:
    return [
        StepResult(
            step=Connect(line_number=1, transport="stdio", target="echo-server"),
            passed=True,
            message="Connected using stdio",
            duration_ms=12.0,
        ),
        StepResult(
            step=Initialize(line_number=2, protocol_version="2025-03-26"),
            passed=True,
            message="Initialized session",
            duration_ms=45.0,
        ),
        StepResult(
            step=ListTools(line_number=3),
            passed=True,
            message="Listed tools",
            duration_ms=8.0,
        ),
        StepResult(
            step=Assert(
                line_number=4,
                query="tools",
                predicate="COUNT",
                expected_value=">= 5",
            ),
            passed=False,
            message="Expected: >= 5, Actual: 3",
            duration_ms=1.0,
            error=AssertionError("Expected: >= 5, Actual: 3"),
        ),
        StepResult(
            step=Shutdown(line_number=5),
            passed=True,
            message="Shutdown completed",
            duration_ms=3.0,
        ),
    ]


def test_console_reporter_all_pass() -> None:
    results = _sample_results()
    results[3] = StepResult(
        step=results[3].step,
        passed=True,
        message="Assertion passed",
        duration_ms=1.0,
    )

    output = ConsoleReporter().report(results)

    assert "✓ CONNECT stdio echo-server" in output
    assert "✓ INITIALIZE protocolVersion=2025-03-26" in output
    assert "✓ LIST tools" in output
    assert "✓ ASSERT tools COUNT >= 5" in output
    assert "5 passed, 0 failed, 0 skipped (69ms)" in output


def test_console_reporter_mixed() -> None:
    output = ConsoleReporter().report(_sample_results())

    assert "✓ CONNECT stdio echo-server" in output
    assert "✗ ASSERT tools COUNT >= 5" in output
    assert "Expected: >= 5, Actual: 3" in output
    assert "4 passed, 1 failed, 0 skipped (69ms)" in output


def test_junit_reporter_structure() -> None:
    xml_output = JUnitReporter().report(_sample_results())
    root = ET.fromstring(xml_output)

    assert root.tag == "testsuite"
    assert root.attrib["name"] == "mcph"
    assert root.attrib["tests"] == "5"
    assert root.attrib["failures"] == "1"
    assert len(root.findall("testcase")) == 5


def test_junit_reporter_failure() -> None:
    xml_output = JUnitReporter().report(_sample_results())
    root = ET.fromstring(xml_output)

    failing_case = next(
        testcase for testcase in root.findall("testcase") if "ASSERT" in testcase.attrib["name"]
    )
    failure = failing_case.find("failure")
    assert failure is not None
    assert failure.attrib["message"] == "Expected: >= 5, Actual: 3"


def test_json_reporter_structure() -> None:
    payload = json.loads(JsonReporter().report(_sample_results()))

    assert payload["version"] == "0.1.0"
    assert payload["file"] == "conformance.mcph"
    assert payload["summary"] == {
        "passed": 4,
        "failed": 1,
        "skipped": 0,
        "duration_ms": 69,
    }
    assert len(payload["steps"]) == 5
    assert payload["steps"][0]["step"] == "CONNECT"


def test_json_reporter_failure() -> None:
    payload = json.loads(JsonReporter().report(_sample_results()))

    failed_steps = [step for step in payload["steps"] if step["passed"] is False]
    assert len(failed_steps) == 1
    assert failed_steps[0]["error"] == "Expected: >= 5, Actual: 3"


def test_write_reports_creates_files(tmp_path) -> None:
    write_reports(_sample_results(), reporters=["junit", "json"], output_dir=str(tmp_path))

    junit_path = tmp_path / "mcph-report.junit.xml"
    json_path = tmp_path / "mcph-report.json"
    assert junit_path.exists()
    assert json_path.exists()

    junit_root = ET.fromstring(junit_path.read_text(encoding="utf-8"))
    json_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert junit_root.tag == "testsuite"
    assert json_payload["summary"]["failed"] == 1


def test_empty_results(tmp_path) -> None:
    console_output = ConsoleReporter().report([])
    assert "0 passed, 0 failed, 0 skipped (0ms)" in console_output

    junit_output = JUnitReporter().report([])
    junit_root = ET.fromstring(junit_output)
    assert junit_root.attrib["tests"] == "0"
    assert junit_root.attrib["failures"] == "0"

    json_output = JsonReporter().report([])
    payload = json.loads(json_output)
    assert payload["summary"]["passed"] == 0
    assert payload["summary"]["failed"] == 0
    assert payload["summary"]["skipped"] == 0

    write_reports([], reporters=["junit", "json"], output_dir=str(tmp_path))
    assert (tmp_path / "mcph-report.junit.xml").exists()
    assert (tmp_path / "mcph-report.json").exists()
