#!/bin/bash

set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

PYTHON="$PROJECT_DIR/.venv/bin/python"
"$PYTHON" -m pip install -r requirements.txt pyinstaller
"$PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name Copyied \
  --osx-bundle-identifier com.copyied.clipboard \
  --distpath "$PROJECT_DIR/dist" \
  --workpath "$PROJECT_DIR/build" \
  "$PROJECT_DIR/app.py"

echo "Created: $PROJECT_DIR/dist/Copyied.app"
