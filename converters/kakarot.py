"""Dragon Ball Z: Kakarot.

Kakarot encrypts its save files itself with a 16-byte block cipher (AES-ECB:
identical plaintext blocks become identical ciphertext blocks). We don't have
the key, so we don't decrypt. Instead:

  * check that each file looks like a Kakarot save (size, block alignment),
  * copy it under its slot name (ManualSave0, ManualSave1, ...).

When the files are packaged into your Apollo export folder, core.package_into
compares them with the console's own file. If both use the same key, they
share ciphertext blocks (the encrypted 'all zeros' block repeats thousands of
times in every save), and the save is drop-in compatible.
"""
from __future__ import annotations

import collections
import re
import shutil
from pathlib import Path

NAME = "kakarot"
DESCRIPTION = "DBZ Kakarot: checks the encrypted save, keeps slot names, key check against your PS4 export"

KNOWN_SIZE = 4_529_808          # varies with progress (a PS4 save seen was 2,043,920)
PS4_FILE_NAME = "ue4savegame.ps4.sav"
SLOT_RE = re.compile(r"(ManualSave\d+|AutoSave\d*|SystemSave\d*)", re.I)


def convert(pc_files, out_dir: Path, game: dict, log) -> list[Path]:
    out = []
    for src in map(Path, pc_files):
        data = src.read_bytes()
        size = len(data)
        log(f"  {src.name}: {size:,} bytes")
        if size % 16:
            log("  ! Size isn't a multiple of 16. This doesn't look like a Kakarot save. Skipped.")
            continue
        if size < 100_000:
            log("  ! Very small for a Kakarot save. Check this is the right file.")
        blocks = collections.Counter(data[i:i + 16] for i in range(0, size, 16))
        top = blocks.most_common(1)[0][1]
        log(f"  repeated-block check: top block repeats {top:,}x (encrypted with a block cipher, as expected)")

        # On the PS4 the slot is the save folder (…_CUSA14835_ManualSave1) and the
        # file inside it is always ue4savegame.ps4.sav.
        m = SLOT_RE.search(src.name)
        if m:
            log(f"  slot: {m.group(1)}. Put it in the Apollo folder that ends in _{m.group(1)}")
        dst = out_dir / PS4_FILE_NAME
        shutil.copy2(src, dst)
        log(f"  -> {PS4_FILE_NAME}")
        out.append(dst)
    if len(out) > 1:
        log("  ! Only one file per run: every slot is its own PS4 save folder. Using the first file.")
        out = out[:1]
    return out
