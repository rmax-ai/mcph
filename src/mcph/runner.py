"""Top-level runner helpers for executing .mcph files."""

from __future__ import annotations

import asyncio
from pathlib import Path

from mcph.parser import parse
from mcph.session import Session, SessionConfig, StepResult


async def run_file(path: str, config: SessionConfig | None = None) -> list[StepResult]:
    """Parse and execute a .mcph file."""
    source = Path(path).read_text(encoding="utf-8")
    test_file = parse(source)
    session = Session(test_file=test_file, config=config or SessionConfig())
    return await session.run()


def run_file_sync(path: str, config: SessionConfig | None = None) -> list[StepResult]:
    """Sync wrapper for CLI use."""
    return asyncio.run(run_file(path=path, config=config))
