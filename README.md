# PS Save Converter

A Windows desktop app that helps you move a game save to a **jailbroken PS4 running
[Apollo Save Tool](https://github.com/bucanero/apollo-ps4)**. It picks the right
PlayStation version (title ID) for the save and puts the files where Apollo expects them.

> This app does **not** do any PlayStation encryption or signing. Apollo does that
> on the console. This app gets the files ready and checks them.

## Features

- **Built-in list of every PS4 game:** 39,000+ titles with title ID and region
  (US / EU / JP / Asia). Search by name (`kakarot`, `gta 5`, `rdr2`) or by ID, double-click a
  game to select every region, and add it in one click. **Update list from internet**
  downloads the latest version.
- **Title ID helper:** understands IDs like `CUSA14835` / `PPSA01234`, cleans up typos
  (`cusa-4947` → `CUSA04947`), and reads the region from content IDs (`UP…` US, `EP…` EU, `JP…`, `HP…`).
- **Version picker:** tells you which version to target (PS4 vs PS5, region,
  disc/digital) and explains why. If your USB stick already has an Apollo export
  of the game, the ID found there wins, because your console created it.
- **USB scan:** finds Apollo save folders on the stick (decrypted, encrypted, or
  empty exports that didn't finish).
- **Safe packaging:** backs up the console's original files first, refuses to write
  into another game's folder, and checks file names and sizes.
- **Key check:** for games that encrypt their own saves with a block cipher, it
  compares your save with the console's file to see if both use the same
  encryption (meaning drop-in compatible) without needing the key.
- **Per-game converter plugins** in `converters/`, plus a template for adding games.

### Supported games

| Game | Converter | Notes |
|---|---|---|
| Dragon Ball Z: Kakarot (`CUSA14835` EU) | `kakarot` | Tested working. Saves become `ue4savegame.ps4.sav`, one PS4 save folder per slot. |
| Any game whose PC and PS4 save data is the same | `generic` | Copy + rename (set a rename map per game). |
| GTA V, RDR2 | `generic` | Experimental: title IDs not verified, needs a real converter. |

Any other PS4 game can be added from the app: **Game** tab → search → **Add selected to my games**.
It starts with the `generic` converter. Manual entries: **Add game**, or edit `games.json`.

## Credits

The PS4 game list (`data/ps4_titles.json`) is built from
[andshrew/supreme-enigma](https://github.com/andshrew/supreme-enigma) (MIT licence),
an extract of Sony's PS5 backwards-compatibility API. Rebuild it with
`python titledb.py PS5-BC-Status.json`, or use the in-app update button.

## Download & run

**Easiest: the .exe (no Python needed)**

1. Go to **Releases** on the right of this page and download `PSSaveConverter.exe` from the latest version.
2. Double-click it. Windows may show "Windows protected your PC" because the exe isn't
   code-signed: click **More info → Run anyway**.

Your games list and the updated title list are saved in `%APPDATA%\PSSaveConverter`,
so they are kept when you download a newer version.

**From source (Python 3.9+)**

1. Install [Python](https://www.python.org/downloads/) (tick **"tcl/tk"** and **"Add to PATH"**).
2. Click **Code → Download ZIP**, unzip it, and double-click **`run.bat`** (or run `python app.py`).

You also need a jailbroken PS4 with Apollo Save Tool and a USB stick (exFAT).

### Building the exe yourself

```
python -m pip install pyinstaller
build_exe.bat
```

The exe appears in `dist\`. Each release's exe is built from the source code of that
release, so you can check the code or build it yourself instead of trusting a download.

## How to use (example: DBZ Kakarot)

1. **On the PS4:** start the game and save in the slot you want to replace.
2. **Apollo → HDD Saves →** that save **→ Copy save game → Copy to USB.**
   You'll get a folder like `PS4/APOLLO/<userid>_CUSA14835_ManualSave1/` on the stick.
3. **On the PC:** open the app.
   - **Game:** pick the game.
   - **Version:** choose console and region, pick the USB drive, press **Scan USB**.
   - **Convert:** add your save file, pick the folder the scan found (only folders for that game are offered), press **CONVERT**.
4. **Back on the PS4: Apollo → USB Saves →** that save **→ Copy save game → Copy to HDD** (overwrite: yes).
   Apollo re-signs the save to your account.
5. Turn off cloud auto-download for the game, start it, and load the same slot.

> ⚠️ For a `<userid>_<TITLEID>_<SLOT>` folder (it has `sce_sys` inside), don't use
> **"Import decrypted save files"**. That only edits the USB copy, and it can overwrite
> your converted file with the old save.

## Adding a game converter

1. Copy `converters/_template.py` to `converters/my_game.py`.
2. Compare a PS4 export with the save you want to move in a hex editor (e.g. HxD).
   Same bytes and a different name means the `generic` converter with a rename map is enough.
   Otherwise, write the conversion (byte swaps, headers, checksums; helpers are in `converters/_helpers.py`).
3. Set `"converter": "my_game"` for the game in `games.json`.

Pull requests with new games and verified title IDs are welcome.

## Disclaimer

Use it only with saves and games you own. **Always keep backups.** A bad save can
crash a game or lose progress. Not affiliated with Sony, PlayStation, Apollo
Save Tool or any game publisher. Provided as is, with no warranty.
