#!/usr/bin/env bash
set -euo pipefail
# Build a single-binary distribution using PyInstaller
uv run pyinstaller --onefile --name mcph src/mcph/cli.py
echo "Binary: dist/mcph"
