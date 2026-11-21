"""Generic converter: copies the PC files and renames them to PS4 names.

Works for games whose PC and PS4 save data is the same (common in Unity/Unreal
games that use their own save format). Rename rules come from the game's
"file_map" in games.json, e.g.  {"SaveSlot*.sav": "SAVEDATA00"}
"""
from __future__ import annotations

import fnmatch
import shutil
from pathlib import Path

NAME = "generic"
DESCRIPTION = "Copy + rename only (for games whose PC and PS4 save data is the same)"


def convert(pc_files, out_dir: Path, game: dict, log) -> list[Path]:
    file_map: dict = game.get("file_map", {}) or {}
    out = []
    for src in map(Path, pc_files):
        new_name = src.name
        for pattern, target in file_map.items():
            if fnmatch.fnmatch(src.name.lower(), pattern.lower()):
                new_name = target
                break
        dst = out_dir / new_name
        shutil.copy2(src, dst)
        log(f"  {src.name}  ->  {new_name}  ({src.stat().st_size:,} bytes)")
        out.append(dst)
    if not file_map:
        log("  (no rename map for this game: file names kept)")
    return out
