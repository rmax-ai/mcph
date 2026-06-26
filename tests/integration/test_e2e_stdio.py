"""End-to-end stdio integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcph.runner import run_file
from mcph.session import SessionConfig


@pytest.mark.asyncio
async def test_e2e_conformance_suite() -> None:
    """Run the conformance.mcph suite against echo-server.py."""
    suite_path = Path(__file__).parent.parent.parent / "examples" / "conformance.mcph"
    config = SessionConfig(timeout=10.0)
    results = await run_file(str(suite_path), config)
    failures = [result for result in results if not result.passed]
    assert len(failures) == 0, f"E2E suite had failures: {failures}"
