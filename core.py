"""Core logic: game database, title-ID parsing, version picker, USB scan, packaging.

No GUI code here so it can be tested and reused from the command line.
"""
from __future__ import annotations

import collections
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "games.json"

# ---------------------------------------------------------------- title IDs

# Known title-ID prefixes. CUSA is used for almost every PS4 game worldwide,
# PPSA for almost every PS5 game. The others are mostly Asian/Japanese
# first-party or disc releases.
PS4_PREFIXES = {
    "CUSA": "PS4 (worldwide)",
    "PLAS": "PS4 (Asia disc)",
    "PCAS": "PS4 (Asia first-party)",
    "PCJS": "PS4 (Japan first-party)",
    "PLJS": "PS4 (Japan disc)",
    "PLJM": "PS4 (Japan disc)",
    "PCKS": "PS4 (Korea first-party)",
}
PS5_PREFIXES = {
    "PPSA": "PS5 (worldwide)",
    "ECAS": "PS5 (Asia first-party)",
    "ELAS": "PS5 (Asia disc)",
    "ELJM": "PS5 (Japan disc)",
    "ECJS": "PS5 (Japan first-party)",
}
# Not \b: folder names like CUSA12345_SAVEDATA00 put '_' (a word char) after the ID.
TITLE_ID_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{4})(\d{5})(?!\d)")

# Content IDs look like UP1004-CUSA00419_00-GTAVDIGITALDOWNL; the first two
# letters give the store region.
CONTENT_REGION = {"UP": "US", "EP": "EU", "JP": "JP", "HP": "Asia", "KP": "Korea", "IP": "Internal"}
CONTENT_ID_RE = re.compile(r"\b([A-Z]{2})\d{4}-([A-Z]{4}\d{5})_\d{2}-[A-Z0-9]{16}\b")


def platform_of(title_id: str) -> str:
    """Return 'PS4', 'PS5' or 'Unknown' for a title ID like CUSA12345."""
    prefix = title_id[:4].upper()
    if prefix in PS4_PREFIXES:
        return "PS4"
    if prefix in PS5_PREFIXES:
        return "PS5"
    return "Unknown"


def normalize_title_id(text: str) -> str | None:
    """Pull a clean title ID out of text such as 'cusa-04947', 'CUSA4947'."""
    t = text.upper().replace("-", "").replace("_", "").replace(" ", "")
    m = re.search(r"([A-Z]{4})(\d{4,5})", t)
    if not m:
        return None
    prefix, num = m.groups()
    return f"{prefix}{int(num):05d}"


def describe_title_id(text: str) -> str:
    tid = normalize_title_id(text)
    if not tid:
        return "Not a valid title ID (expected 4 letters + 5 digits, e.g. CUSA04947)."
    prefix = tid[:4]
    kind = PS4_PREFIXES.get(prefix) or PS5_PREFIXES.get(prefix) or "unknown prefix"
    lines = [f"{tid}: {kind}"]
    cm = CONTENT_ID_RE.search(text.upper())
    if cm:
        lines.append(f"Store region: {CONTENT_REGION.get(cm.group(1), cm.group(1))}")
    if text.strip().upper() != tid:
        lines.append(f"(normalised from '{text.strip()}')")
    return "\n".join(lines)


# ---------------------------------------------------------------- database

def load_db() -> dict:
    if not DB_PATH.exists():
        return {"games": []}
    with open(DB_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_db(db: dict) -> None:
    tmp = DB_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)
    os.replace(tmp, DB_PATH)


def find_game(db: dict, name: str) -> dict | None:
    n = name.strip().lower()
    for g in db["games"]:
        if g["name"].lower() == n or n in (a.lower() for a in g.get("aliases", [])):
            return g
    return None


# ---------------------------------------------------------------- USB scan

@dataclass
class SaveFolder:
    """A save folder found on a USB stick / folder (from an Apollo export)."""
    title_id: str
    path: Path
    files: list[str] = field(default_factory=list)
    kind: str = "decrypted"  # 'decrypted' or 'encrypted'

    def label(self) -> str:
        return f"{self.title_id} [{self.kind}]  {self.path}  ({len(self.files)} files)"


def _looks_encrypted(folder: Path) -> bool:
    # Encrypted PS4 saves exported by Apollo come as <name> + <name>.bin pairs
    # (sealed key + image). Decrypted exports are the game's own files.
    names = {p.name for p in folder.iterdir() if p.is_file()}
    return any(n.endswith(".bin") and n[:-4] in names for n in names)


def scan_for_saves(root: Path, max_depth: int = 5) -> list[SaveFolder]:
    """Walk `root` looking for folders whose name contains a title ID.

    Apollo puts exported saves under paths like
      USB:/PS4/APOLLO/CUSA12345_SAVEDATA00/   (encrypted copy)
      USB:/PS4/APOLLO/CUSA12345/<save dir>/   (decrypted export)
    The exact layout differs between Apollo versions, so instead of
    hard-coding it we find whatever is actually on the stick.
    """
    found: list[SaveFolder] = []
    root = Path(root)
    if not root.exists():
        return found
    root_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = len(Path(dirpath).parts) - root_depth
        if depth >= max_depth:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if not d.startswith(("$", "System Volume", "_backup_"))]
        here = Path(dirpath)
        # Folder named with a title ID (CUSA12345 or CUSA12345_SAVEDATA00), or a
        # save dir directly inside such a folder.
        tid = None
        for part in (here.name, here.parent.name):
            m = TITLE_ID_RE.search(part.upper())
            if m and platform_of(m.group(0)) != "Unknown":
                tid = m.group(0)
                break
        if tid and here.name.lower() != "sce_sys":
            files = sorted(f for f in filenames if not f.startswith("."))
            if not files and not dirnames:
                kind = "empty"   # Apollo export that didn't finish / failed
            elif not files:
                continue
            else:
                kind = "encrypted" if _looks_encrypted(here) else "decrypted"
            found.append(SaveFolder(tid, here, files, kind))
    return found


# ---------------------------------------------------------------- version picker

@dataclass
class Recommendation:
    title_id: str | None
    reasons: list[str]
    warnings: list[str]
    candidates: list[dict]


def recommend_version(game: dict, console: str, region: str, edition: str,
                      usb_found: list[SaveFolder] | None = None) -> Recommendation:
    """Decide which PlayStation version (title ID) the converted save must target.

    console: 'PS4 (jailbroken, Apollo)' | 'PS5 playing the PS4 version' | 'PS5 (PS5 version)'
    region:  'US' | 'EU' | 'JP' | 'Asia' | 'Any'
    edition: 'Disc' | 'Digital' | 'Any'
    """
    reasons: list[str] = []
    warnings: list[str] = []
    versions = game.get("versions", [])

    # 1. Platform: Apollo on a jailbroken PS4 can only re-sign PS4 saves.
    if console.startswith("PS5 (PS5"):
        want_platform = "PS5"
        warnings.append("A jailbroken PS4 with Apollo can't re-sign PS5 (PPSA) saves. "
                        "You need a jailbroken PS5 for that. Many games also let you "
                        "upload the PS4 save and continue it in the PS5 version.")
    else:
        want_platform = "PS4"
        reasons.append("Apollo on PS4 re-signs PS4 saves, so the target must be a PS4 title ID "
                       "(CUSA..., or PLAS/PCJS... in Asia/Japan).")
        if console.startswith("PS5 playing"):
            reasons.append("PS5 plays PS4 games through backward compatibility, and PS4 saves "
                           "work there too. Re-sign on the PS4, then move the save over with "
                           "PS Plus cloud saves or by playing that game on the PS4.")

    cands = [v for v in versions if v.get("platform", platform_of(v["title_id"])) == want_platform]
    if not cands:
        warnings.append(f"No {want_platform} title IDs for this game in the database yet. Add them, "
                        "or use Scan USB.")

    # 2. Region: the save has to match the copy you own.
    if region != "Any" and cands:
        by_region = [v for v in cands if v.get("region", "").lower() == region.lower()]
        if by_region:
            cands = by_region
            reasons.append(f"Region {region}: a save only loads under the title ID of the copy "
                           "you own (disc region, or your PSN store region for digital).")
        else:
            warnings.append(f"No {region} version in the database. The candidates below are "
                            "from other regions and probably won't load.")

    # 3. Edition: some games use different IDs for disc and digital.
    if edition != "Any" and len(cands) > 1:
        by_ed = [v for v in cands if edition.lower() in v.get("edition", "").lower()]
        if by_ed:
            cands = by_ed
            reasons.append(f"Edition {edition}: picked the matching release.")

    # 4. USB scan is ground truth: it is the ID your console actually created.
    chosen = None
    if usb_found:
        known = {v["title_id"] for v in versions}
        on_usb = [s for s in usb_found if platform_of(s.title_id) == want_platform]
        match = [s for s in on_usb if s.title_id in known] or (on_usb if not known else [])
        if match:
            chosen = match[0].title_id
            reasons.insert(0, f"Found {chosen} on your USB. Your console made that save, so it's "
                              "the right ID (this beats every other rule).")
            if chosen not in {v["title_id"] for v in cands}:
                warnings.append("The ID on your USB doesn't match the region/edition you "
                                "picked. Trust the USB.")
    if chosen is None and cands:
        chosen = cands[0]["title_id"]
        if len(cands) > 1:
            warnings.append("More than one version matches. Scan your USB to know for sure.")
        if not cands[0].get("verified", False):
            warnings.append(f"{chosen} hasn't been verified. Confirm it on the console: "
                            "the game's Information screen, or Scan USB after an Apollo copy.")

    return Recommendation(chosen, reasons, warnings, cands)


# ---------------------------------------------------------------- packaging

def same_block_encryption(console: bytes, pc: bytes, top_n: int = 8) -> tuple[bool, str]:
    """Do two block-cipher (ECB) saves use the same key?

    The most-repeated 16-byte ciphertext blocks are encrypted runs of
    identical plaintext (usually zeros). With the same key they show up in
    both files; with a different key they never match.
    """
    def top(d):
        c = collections.Counter(d[i:i + 16] for i in range(0, len(d) - len(d) % 16, 16))
        return [b for b, n in c.most_common(top_n) if n > 4]
    a, b = top(console), set(top(pc))
    if not a:
        return False, "the console file has no repeated blocks, so the check can't run"
    shared = sum(1 for blk in a if blk in b)
    if shared:
        return True, f"{shared} of the console file's {len(a)} most common encrypted blocks also appear in yours"
    return False, "none of the console file's common encrypted blocks appear in yours"


@dataclass
class PackageResult:
    target: Path
    written: list[str]
    backup: Path | None
    warnings: list[str]


def package_into(staged: list[Path], target: Path, existing: SaveFolder | None) -> PackageResult:
    """Copy converted files into the Apollo decrypted-save folder.

    If the folder already holds the console's exported files, they're backed
    up first, and the names and sizes are checked against what the console
    expects.
    """
    target.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    backup = None

    current = [p for p in target.iterdir() if p.is_file()]
    if current:
        backup = target.parent / f"_backup_{target.name}_{datetime.now():%Y%m%d_%H%M%S}"
        backup.mkdir()
        for p in current:
            shutil.copy2(p, backup / p.name)

    if existing and existing.kind == "encrypted":
        warnings.append("That folder is an ENCRYPTED copy. Writing decrypted files there won't "
                        "work. In Apollo use 'Export decrypted save files', then pick that folder.")

    expected = {p.name: p.stat().st_size for p in current}
    rename = {}
    # One file in, one file in the console's folder with another name: the
    # console's name is the one the game looks for.
    if len(staged) == 1 and len(expected) == 1 and staged[0].name not in expected:
        only = next(iter(expected))
        rename[staged[0].name] = only
        warnings.append(f"Renamed '{staged[0].name}' to '{only}' to match the console's file.")
    written = []
    for src in staged:
        name = rename.get(src.name, src.name)
        if name in expected and backup:
            ok, why = same_block_encryption((backup / name).read_bytes(), src.read_bytes())
            if "can't run" in why:
                warnings.append(f"KEY CHECK SKIPPED: {why}.")
            elif ok:
                warnings.append(f"KEY CHECK PASSED: same encryption as your PS4 save ({why}).")
            else:
                warnings.append("KEY CHECK FAILED: different encryption from your PS4 save, the game "
                                f"will probably reject it ({why}).")
        dst = target / name
        shutil.copy2(src, dst)
        written.append(name)
        if expected:
            if name not in expected:
                warnings.append(f"'{name}' isn't one of the files the console exported "
                                f"({', '.join(sorted(expected))}). The game probably won't find "
                                "it. Fix the file names (the rename map in the game entry).")
            else:
                old, new = expected[name], src.stat().st_size
                key_ok = any(w.startswith("KEY CHECK PASSED") for w in warnings)
                if key_ok and new > old:
                    warnings.append(f"NOTE: your file ({new:,} bytes) is bigger than the console's ({old:,}). "
                                    "Same format, so that's fine, but if Apollo says there isn't enough "
                                    "space, play further on the PS4 to get a bigger save and export again.")
                elif not key_ok and old and abs(new - old) / old > 0.25:
                    warnings.append(f"'{name}' is {new:,} bytes and the console's file is "
                                    f"{old:,} bytes. A big size gap usually means the format "
                                    "isn't converted yet.")
    if expected:
        missing = sorted(set(expected) - set(written))
        if missing:
            warnings.append("The console's files that weren't replaced (kept as is): "
                            + ", ".join(missing))
    return PackageResult(target, written, backup, warnings)
