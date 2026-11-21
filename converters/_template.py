"""TEMPLATE: copy this file to e.g. converters/my_game.py and edit it.

Then set "converter": "my_game" for that game in games.json (or in the app).

How to work out what a game needs:
  1. On the PS4, use Apollo to "Export decrypted save files" to USB.
  2. Compare that PS4 file with your PC file in a hex editor (HxD is free).
     - Same bytes, different name  -> the generic converter + a file_map is enough.
     - Same layout, bytes reversed -> swap32/swap16 (endianness).
     - Different header             -> copy the PS4 header, keep the PC body.
     - Checksum at a fixed offset   -> recompute it after editing (crc32/md5/...).
     - Compressed/encrypted body    -> the game encrypts its saves itself; you
       need the game's own key/algorithm (search the game's modding community).
"""
from __future__ import annotations

from pathlib import Path

from ._helpers import swap32, crc32, put_u32  # noqa: F401

NAME = "my_game"
DESCRIPTION = "Template - describe the conversion here"

PS4_FILE_NAME = "SAVEDATA00"   # name the PS4 game expects
HEADER_SIZE = 0x10             # example: bytes of header before the payload
CHECKSUM_OFFSET = 0x0C         # example: where the CRC32 lives


def convert(pc_files, out_dir: Path, game: dict, log) -> list[Path]:
    out = []
    for src in map(Path, pc_files):
        data = bytearray(src.read_bytes())

        # --- example steps, replace with what your game really needs ---
        # data[HEADER_SIZE:] = swap32(bytes(data[HEADER_SIZE:]))
        # put_u32(data, CHECKSUM_OFFSET, crc32(bytes(data[HEADER_SIZE:])))

        dst = out_dir / PS4_FILE_NAME
        dst.write_bytes(data)
        log(f"  {src.name} -> {dst.name}")
        out.append(dst)
    return out
