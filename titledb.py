"""Built-in list of PS4 games (title ID, name, region).

Source: andshrew/supreme-enigma (MIT licence), an extract of Sony's PS5
backwards-compatibility API with every known CUSA title ID.
https://github.com/andshrew/supreme-enigma

The app ships a compact copy in data/ps4_titles.json and can refresh it.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

SOURCE_URL = "https://raw.githubusercontent.com/andshrew/supreme-enigma/master/docs/PS5-BC-Status.json"
import paths

# Copied to %APPDATA% on first run of the .exe so "Update list" can overwrite it.
DATA_PATH = paths.user_file("data/ps4_titles.json")

# Sony store region prefixes -> the names the app uses.
REGION_NAMES = {"UP": "US", "EP": "EU", "JP": "JP", "HP": "Asia", "KP": "Asia", "IP": "Internal"}
ID_PREFIXES = {"CUSA", "PLAS", "PCAS", "PCJS", "PLJS", "PLJM", "PCKS", "PPSA", "ECAS", "ELAS", "ELJM", "ECJS"}
_DEMO_RE =re.compile(r"\b(demo|trial|beta|体験版)\b|体験版", re.I)


def is_demo(name: str) -> bool:
    return bool(_DEMO_RE.search(name))


def _norm(s: str) -> str:
    return re.sub(r"[^0-9a-z]+", " ", s.lower()).strip()


# Short names people type -> words in the store name.
ABBREVIATIONS = {
    "gta": "grand theft auto", "rdr": "red dead redemption", "dbz": "dragon ball z",
    "cod": "call of duty", "ff": "final fantasy", "mgs": "metal gear solid",
    "re": "resident evil", "ac": "assassin s creed", "nfs": "need for speed",
    "gow": "god of war", "tlou": "the last of us", "kh": "kingdom hearts",
    "mk": "mortal kombat", "nba": "nba", "rdr2": "red dead redemption 2",
    "gtav": "grand theft auto v", "gta5": "grand theft auto v", "gta 5": "grand theft auto v",
}
_ROMAN = {"2": "ii", "3": "iii", "4": "iv", "5": "v", "6": "vi", "7": "vii"}


def _expand(q: str) -> list[str]:
    """Return the query plus versions with abbreviations / roman numerals swapped."""
    n = _norm(q)
    variants = {n}
    if n in ABBREVIATIONS:
        variants.add(ABBREVIATIONS[n])
    words = n.split()
    exp = [ABBREVIATIONS.get(w, w) for w in words]
    variants.add(" ".join(exp))
    for v in list(variants):
        variants.add(" ".join(_ROMAN.get(w, w) for w in v.split()))
    return [v for v in variants if v]


def convert_source(raw: list) -> list:
    """Turn the source JSON into compact rows: [title_id, name, region]."""
    rows = {}
    for x in raw:
        tid = (x.get("npTitleIdshort") or x.get("npTitleId", "")[:9]).upper()
        name = (x.get("name") or "").strip()
        if not re.fullmatch(r"[A-Z]{4}\d{5}", tid) or not name:
            continue
        rows[tid] = [tid, name, REGION_NAMES.get(x.get("region", ""), x.get("region", "") or "?")]
    return sorted(rows.values())


class TitleDB:
    def __init__(self, path: Path = DATA_PATH):
        self.path = path
        self.rows: list = []
        self.by_id: dict = {}
        self.load()

    def load(self):
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                self.rows = json.load(f)["titles"]
        self.by_id = {r[0]: r for r in self.rows}

    def __len__(self):
        return len(self.rows)

    def lookup(self, title_id: str):
        return self.by_id.get(title_id.upper())

    def search(self, query: str, limit: int = 300, include_demos: bool = False) -> list:
        """Search by name words or by title ID. Exact-ish matches first."""
        q = query.strip()
        if not q:
            return []
        m = re.fullmatch(r"([A-Za-z]{4})-?(\d{1,5})", q.replace(" ", ""))
        if m and m.group(1).upper() in ID_PREFIXES:   # 'FIFA 23' is a name, not an ID
            tid = f"{m.group(1).upper()}{int(m.group(2)):05d}"
            r = self.lookup(tid)
            if r:
                return [r]
            pre = m.group(1).upper() + m.group(2)
            return [r for r in self.rows if r[0].startswith(pre)][:limit]
        variants = [v.split() for v in _expand(q)]
        out = []
        for r in self.rows:
            n = " " + _norm(r[1]) + " "
            # whole-word match, so 'v' doesn't match every title with a v in it
            if any(all(f" {w} " in n or (len(w) > 3 and w in n) for w in ws) for ws in variants) \
                    or q.lower() in r[1].lower():
                if include_demos or not is_demo(r[1]):
                    out.append(r)
        targets = [" ".join(ws) for ws in variants]
        out.sort(key=lambda r: (_norm(r[1]) not in targets,
                                # "Marvel's Spider-Man" before "Spider-Man: Homecoming VR"
                                not any(_norm(r[1]).endswith(t) for t in targets),
                                not any(_norm(r[1]).startswith(t) for t in targets),
                                len(r[1]), r[1], r[2]))
        return out[:limit]

    def same_game(self, name: str) -> list:
        """Every region's release with exactly this name (demos excluded)."""
        n = _norm(name)
        return [r for r in self.rows if _norm(r[1]) == n and not is_demo(r[1])]

    def update_from_internet(self, url: str = SOURCE_URL, timeout: int = 60) -> int:
        req = urllib.request.Request(url, headers={"User-Agent": "PSSaveConverter"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        rows = convert_source(raw)
        if len(rows) < 1000:
            raise ValueError(f"Download looks wrong (only {len(rows)} titles). Kept the old list.")
        save(rows, self.path)
        self.load()
        return len(rows)


def save(rows: list, path: Path = DATA_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"source": "https://github.com/andshrew/supreme-enigma (MIT)",
                   "fields": ["title_id", "name", "region"], "titles": rows},
                  f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


if __name__ == "__main__":
    # python titledb.py <downloaded PS5-BC-Status.json>   -> builds data/ps4_titles.json
    import sys
    with open(sys.argv[1], encoding="utf-8") as f:
        rows = convert_source(json.load(f))
    save(rows)
    print(f"saved {len(rows)} titles to {DATA_PATH}")
