from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
REQUIREMENTS = ROOT / "requirements.txt"


def ensure_dependencies() -> None:
    try:
        import customtkinter  # noqa: F401
    except Exception:
        installer = PYTHON if PYTHON.exists() else Path(sys.executable)
        subprocess.run([str(installer), "-m", "pip", "install", "-r", str(REQUIREMENTS)], cwd=ROOT, check=False)


ensure_dependencies()
from app import LinkClipWidget  # noqa: E402


LinkClipWidget().mainloop()
