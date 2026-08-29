#!/bin/bash

set -u
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

PYTHON="$PROJECT_DIR/.venv/bin/python"
if ! "$PYTHON" -c "import customtkinter" >/dev/null 2>&1; then
  "$PYTHON" -m pip install -r "$PROJECT_DIR/requirements.txt"
fi

exec "$PYTHON" "$PROJECT_DIR/app.py"
