"""Where the app's files live, both from source and as a packaged .exe.

BUNDLE_DIR: read-only files shipped with the app (default games.json, title list).
USER_DIR:   files the app writes (your games list, updated title list).

Run from source, both are the project folder (same as before).
Run as an .exe, the bundled files are unpacked to a temporary folder each
start, so anything the app saves goes to %APPDATA%\\PSSaveConverter instead.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    USER_DIR = Path(os.environ.get("APPDATA", Path.home())) / "PSSaveConverter"
else:
    BUNDLE_DIR = USER_DIR = Path(__file__).resolve().parent


def user_file(rel: str) -> Path:
    """Path of a writable file. On first run of the .exe it starts as a copy of
    the bundled default, so the user's edits survive restarts and updates."""
    dst = USER_DIR / rel
    if FROZEN and not dst.exists():
        src = BUNDLE_DIR / rel
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return dst
