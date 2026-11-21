"""Converter plugins.

Each module in this folder (not starting with '_') is a converter. It must
define:

    NAME = "my_game"                     # used in games.json "converter"
    DESCRIPTION = "What it does"
    def convert(pc_files, out_dir, game, log) -> list[Path]

`pc_files` are the PC save files the user picked, `out_dir` is an empty
staging folder, `game` is the game's entry from games.json and `log(str)`
prints to the app's log. Return the files written to out_dir; the app then
copies them into the Apollo folder.

Copy _template.py to start a new game.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path


def available() -> dict:
    mods = {}
    for info in pkgutil.iter_modules([str(Path(__file__).parent)]):
        if info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{info.name}")
        if hasattr(mod, "convert"):
            mods[getattr(mod, "NAME", info.name)] = mod
    return mods
