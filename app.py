"""PS Save Converter - desktop app (Tkinter).

Run:  python app.py   (or double-click run.bat)
"""
from __future__ import annotations

import shutil
import tempfile
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import threading

import converters
import core
import titledb

CONSOLES = ["PS4 (jailbroken, Apollo)", "PS5 playing the PS4 version", "PS5 (PS5 version)"]
REGIONS = ["US", "EU", "JP", "Asia", "Any"]
EDITIONS = ["Any", "Disc", "Digital"]

HELP_TEXT = """HOW IT WORKS (jailbroken PS4 + Apollo Save Tool)

PS4 saves are encrypted and signed to your account. This app does NOT do
the encryption. Apollo does that on the console. This app gets the
decrypted files ready.

 1. On the PS4: start the game once and save, so a save already exists.
 2. In Apollo: HDD Saves > that save > "Copy save game" > "Copy to
    USB". You get a folder like 131dab3e_CUSA14835_ManualSave1.
 3. Plug the USB into the PC. On the Version tab, pick your console and
    region, then press "Scan USB". The title ID found on the USB is the
    one your console really uses (e.g. CUSA04947), so the app trusts it.
 4. Convert tab: add your PC save file(s), pick the folder the scan
    found, press Convert. The console's original files are backed up
    next to it (_backup_...).
 5. Put the USB back in the PS4. Which Apollo step depends on the
    folder you converted into:
    - Folder named like 131dab3e_CUSA14835_ManualSave1 (has sce_sys
      inside): that's a full save copy on the USB. In Apollo go to
      USB Saves > that save > "Copy save game" > "Copy to HDD" and
      say yes to overwrite. That puts it on the PS4 and re-signs it.
      ("Import decrypted" here only edits the copy on the USB.)
    - Otherwise: HDD Saves > the save > "Import decrypted save files".
 6. Turn off cloud auto-download for the game, start it, and load
    the same slot.

PICKING THE RIGHT VERSION
 - CUSAxxxxx = PS4 game, PPSAxxxxx = PS5 game.
 - Each region (US/EU/JP/Asia) has its own ID. The save must match the
   copy you own. Sometimes disc and digital differ too.
 - Apollo on PS4 can only target PS4 (CUSA...) IDs.
 - A PS5 plays PS4 games with PS4 saves, so the PS4 version is the one
   that works with this setup.

ABOUT CONVERSION
 Every game saves differently. The 'generic' converter only copies and
 renames, which is enough when the PC and PS4 data is the same. For
 other games, copy converters/_template.py and write the real
 conversion (byte swaps, headers, checksums). Compare a PS4 export with
 your PC save in a hex editor to see what's different.
 Back up everything first. A bad save can crash the game, but your
 Apollo backup lets you restore it.
"""


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PS Save Converter - PC to PS4/PS5")
        self.geometry("980x780")
        self.minsize(800, 640)
        self.db = core.load_db()
        self.tdb = titledb.TitleDB()
        self.convs = converters.available()
        self.usb_found: list[core.SaveFolder] = []
        self.recommended: str | None = None
        self.pc_files: list[Path] = []

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.nb = nb
        self._build_game_tab(nb)
        self._build_version_tab(nb)
        self._build_convert_tab(nb)
        self._build_help_tab(nb)
        self._refresh_games()

    # ------------------------------------------------------------- helpers
    @property
    def game(self) -> dict | None:
        sel = self.game_list.curselection()
        if not sel:
            return None
        return self.db["games"][sel[0]]

    @staticmethod
    def _set_text(widget: tk.Text, text: str):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.config(state="disabled")

    def log(self, msg: str):
        self.log_box.config(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")
        self.update_idletasks()

    # ------------------------------------------------------------- tab 1
    def _build_game_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="1. Game")

        # ---- search the built-in list of every PS4 game
        s = ttk.LabelFrame(f, text="", padding=6)
        s.pack(side="top", fill="x", pady=(0, 8))
        self.search_frame = s
        row = ttk.Frame(s)
        row.pack(fill="x")
        self.search_var = tk.StringVar()
        e = ttk.Entry(row, textvariable=self.search_var, width=40)
        e.pack(side="left")
        e.bind("<Return>", lambda ev: self._search())
        ttk.Button(row, text="Search", command=self._search).pack(side="left", padx=4)
        self.demos_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="Show demos/betas", variable=self.demos_var,
                        command=self._search).pack(side="left", padx=6)
        self.update_btn = ttk.Button(row, text="Update list from internet", command=self._update_titles)
        self.update_btn.pack(side="right")

        cols = ("id", "name", "region")
        self.results = ttk.Treeview(s, columns=cols, show="headings", height=6, selectmode="extended")
        for c, w, label in (("id", 100, "Title ID"), ("name", 420, "Name"), ("region", 70, "Region")):
            self.results.heading(c, text=label)
            self.results.column(c, width=w, stretch=(c == "name"))
        self.results.pack(fill="x", pady=4)
        self.results.bind("<Double-1>", lambda ev: self._select_all_regions())
        row2 = ttk.Frame(s)
        row2.pack(fill="x")
        ttk.Button(row2, text="Add selected to my games", command=self._add_from_search).pack(side="left")
        ttk.Label(row2, text="Tip: double-click a game to select it in every region (US/EU/JP/Asia).",
                  foreground="#666").pack(side="left", padx=8)
        self._update_search_title()

        left = ttk.Frame(f)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Games").pack(anchor="w")
        self.game_list = tk.Listbox(left, width=32, height=10, exportselection=False)
        self.game_list.pack(fill="y", expand=True)
        self.game_list.bind("<<ListboxSelect>>", lambda e: self._show_game())
        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=4)
        ttk.Button(btns, text="Add game", command=lambda: self._edit_game(None)).pack(side="left")
        ttk.Button(btns, text="Edit", command=lambda: self.game and self._edit_game(self.game)).pack(side="left", padx=4)
        ttk.Button(btns, text="Delete", command=self._delete_game).pack(side="left")

        right = ttk.Frame(f, padding=(10, 0, 0, 0))
        right.pack(side="left", fill="both", expand=True)
        ttk.Label(right, text="Details").pack(anchor="w")
        self.game_info = tk.Text(right, height=16, wrap="word", state="disabled")
        self.game_info.pack(fill="both", expand=True)

        chk = ttk.LabelFrame(right, text="Title ID checker (type e.g. CUSA4947 or a content ID)", padding=6)
        chk.pack(fill="x", pady=(8, 0))
        self.tid_entry = ttk.Entry(chk)
        self.tid_entry.pack(side="left", fill="x", expand=True)
        self.tid_entry.bind("<Return>", lambda e: self._check_tid())
        ttk.Button(chk, text="Check", command=self._check_tid).pack(side="left", padx=4)
        self.tid_result = ttk.Label(right, text="", foreground="#0a5")
        self.tid_result.pack(anchor="w", pady=4)

    def _refresh_games(self, select: int | None = 0):
        self.game_list.delete(0, "end")
        for g in self.db["games"]:
            self.game_list.insert("end", g["name"])
        if select is not None and self.db["games"]:
            select = min(select, len(self.db["games"]) - 1)
            self.game_list.selection_set(select)
            self._show_game()

    def _show_game(self):
        g = self.game
        if not g:
            return
        lines = [g["name"]]
        if g.get("aliases"):
            lines.append("Also known as: " + ", ".join(g["aliases"]))
        lines += ["", "Versions:"]
        for v in g.get("versions", []):
            mark = "verified" if v.get("verified") else "NOT verified"
            lines.append(f"  {v['title_id']}  {v.get('platform', core.platform_of(v['title_id']))}  "
                         f"{v.get('region', '?')}  {v.get('edition', '')}  [{mark}]")
        lines += ["", f"Converter: {g.get('converter', 'generic')}"]
        if g.get("file_map"):
            lines.append("Rename map: " + ", ".join(f"{k} -> {v}" for k, v in g["file_map"].items()))
        if g.get("pc_save_hint"):
            lines.append(f"PC save location: {g['pc_save_hint']}")
        if g.get("notes"):
            lines += ["", "Notes: " + g["notes"]]
        self._set_text(self.game_info, "\n".join(lines))
        if hasattr(self, "conv_combo"):
            self.conv_var.set(g.get("converter", "generic"))
            self._refresh_targets()

    def _check_tid(self):
        text = core.describe_title_id(self.tid_entry.get())
        tid = core.normalize_title_id(self.tid_entry.get())
        r = self.tdb.lookup(tid) if tid else None
        if r:
            text += f"\nGame: {r[1]}  (region {r[2]})"
        elif tid:
            text += "\n(not in the built-in game list)"
        self.tid_result.config(text=text)

    # ---- built-in title list
    def _update_search_title(self):
        self.search_frame.config(text=f"Find any PS4 game ({len(self.tdb):,} titles, every region). "
                                      "Type a name or a title ID")

    def _search(self):
        self.results.delete(*self.results.get_children())
        for tid, name, region in self.tdb.search(self.search_var.get(), include_demos=self.demos_var.get()):
            self.results.insert("", "end", iid=tid, values=(tid, name, region))

    def _select_all_regions(self):
        sel = self.results.selection()
        if not sel:
            return
        name = self.results.item(sel[0], "values")[1]
        same = {r[0] for r in self.tdb.same_game(name)} | set(sel)
        for tid, n, reg in self.tdb.same_game(name):
            if not self.results.exists(tid):
                self.results.insert("", "end", iid=tid, values=(tid, n, reg))
        self.results.selection_set([i for i in same if self.results.exists(i)])

    def _add_from_search(self):
        sel = self.results.selection()
        if not sel:
            return messagebox.showinfo("Add game", "Select one or more rows first (double-click selects "
                                       "every region of a game).")
        rows = [self.results.item(i, "values") for i in sel]
        # Use an English name if there is one (JP releases have Japanese names).
        names = [r[1] for r in rows]
        name = next((n for n in names if n.isascii()), names[0]).replace("™", "").replace("®", "").strip()
        versions = [{"title_id": tid, "platform": core.platform_of(tid), "region": reg,
                     "edition": "", "verified": True} for tid, _, reg in rows]
        game = core.find_game(self.db, name)
        if game:
            have = {v["title_id"] for v in game.get("versions", [])}
            added = [v for v in versions if v["title_id"] not in have]
            for v in game["versions"]:     # IDs confirmed by the list
                if v["title_id"] in {x["title_id"] for x in versions}:
                    v["verified"] = True
            game["versions"].extend(added)
            msg = f"{name} is already in your games. Added {len(added)} new version(s)."
        else:
            game = {"name": name, "aliases": [], "pc_save_hint": "", "converter": "generic",
                    "file_map": {}, "notes": "Added from the built-in game list.", "versions": versions}
            self.db["games"].append(game)
            msg = f"Added {name} with {len(versions)} version(s)."
        core.save_db(self.db)
        self._refresh_games(select=self.db["games"].index(game))
        messagebox.showinfo("Add game", msg)

    def _update_titles(self):
        self.update_btn.config(state="disabled", text="Downloading...")

        def work():
            try:
                n = self.tdb.update_from_internet()
                msg = f"Game list updated: {n:,} titles."
            except Exception as e:
                msg = f"Couldn't update the game list: {e}"
            self.after(0, lambda: done(msg))

        def done(msg):
            self.update_btn.config(state="normal", text="Update list from internet")
            self._update_search_title()
            messagebox.showinfo("Game list", msg)

        threading.Thread(target=work, daemon=True).start()

    def _delete_game(self):
        g = self.game
        if g and messagebox.askyesno("Delete", f"Remove {g['name']} from the database?"):
            self.db["games"].remove(g)
            core.save_db(self.db)
            self._refresh_games()

    def _edit_game(self, game: dict | None):
        GameDialog(self, game)

    # ------------------------------------------------------------- tab 2
    def _build_version_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="2. Version")
        form = ttk.Frame(f)
        form.pack(fill="x")
        self.console_var = tk.StringVar(value=CONSOLES[0])
        self.region_var = tk.StringVar(value="US")
        self.edition_var = tk.StringVar(value="Any")
        self.usb_var = tk.StringVar()
        rows = [("Console you'll play on", ttk.Combobox(form, textvariable=self.console_var, values=CONSOLES, state="readonly", width=34)),
                ("Region of your copy", ttk.Combobox(form, textvariable=self.region_var, values=REGIONS, state="readonly", width=34)),
                ("Disc or digital", ttk.Combobox(form, textvariable=self.edition_var, values=EDITIONS, state="readonly", width=34))]
        for i, (lbl, w) in enumerate(rows):
            ttk.Label(form, text=lbl).grid(row=i, column=0, sticky="w", pady=3)
            w.grid(row=i, column=1, sticky="w", pady=3)
        ttk.Label(form, text="USB drive / folder").grid(row=3, column=0, sticky="w", pady=3)
        usb_row = ttk.Frame(form)
        usb_row.grid(row=3, column=1, sticky="we")
        ttk.Entry(usb_row, textvariable=self.usb_var, width=40).pack(side="left")
        ttk.Button(usb_row, text="Browse", command=self._pick_usb).pack(side="left", padx=4)
        ttk.Button(usb_row, text="Scan USB", command=self._scan_usb).pack(side="left")

        ttk.Button(f, text="Recommend version", command=self._recommend).pack(anchor="w", pady=8)
        self.rec_box = tk.Text(f, height=20, wrap="word", state="disabled")
        self.rec_box.pack(fill="both", expand=True)

    def _pick_usb(self):
        d = filedialog.askdirectory(title="Pick your USB drive (or the folder Apollo exported to)")
        if d:
            self.usb_var.set(d)

    def _scan_usb(self):
        root = self.usb_var.get().strip()
        if not root:
            self._pick_usb()
            root = self.usb_var.get().strip()
            if not root:
                return
        self.usb_found = core.scan_for_saves(Path(root))
        self._refresh_targets()
        if not self.usb_found:
            messagebox.showinfo("Scan USB", "No PlayStation save folders found.\n\nIn Apollo use "
                                "'Export decrypted save files' to USB first.")
        else:
            self._recommend()

    def _recommend(self):
        g = self.game
        if not g:
            messagebox.showwarning("No game", "Pick a game on the Game tab first.")
            return
        rec = core.recommend_version(g, self.console_var.get(), self.region_var.get(),
                                     self.edition_var.get(), self.usb_found)
        self.recommended = rec.title_id
        out = [f"Game: {g['name']}", "",
               f"USE THIS VERSION:  {rec.title_id or '(could not decide)'}"]
        if rec.title_id:
            out.append(f"  -> {core.describe_title_id(rec.title_id)}")
        out += ["", "Why:"] + [f"  - {r}" for r in rec.reasons]
        if rec.warnings:
            out += ["", "Warnings:"] + [f"  ! {w}" for w in rec.warnings]
        if rec.candidates:
            out += ["", "Matching versions in database:"]
            out += [f"  {v['title_id']}  {v.get('region', '?')}  {v.get('edition', '')}" for v in rec.candidates]
        if self.usb_found:
            out += ["", "Found on USB:"]
            for s in self.usb_found:
                r = self.tdb.lookup(s.title_id)
                out.append(f"  {s.label()}" + (f"   = {r[1]} ({r[2]})" if r else ""))
        self._set_text(self.rec_box, "\n".join(out))

    # ------------------------------------------------------------- tab 3
    def _build_convert_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="3. Convert")

        a = ttk.LabelFrame(f, text="PC save file(s)", padding=6)
        a.pack(fill="x")
        self.pc_list = tk.Listbox(a, height=4)
        self.pc_list.pack(side="left", fill="x", expand=True)
        b = ttk.Frame(a)
        b.pack(side="left", padx=4)
        ttk.Button(b, text="Add files", command=self._add_pc).pack(fill="x")
        ttk.Button(b, text="Clear", command=self._clear_pc).pack(fill="x", pady=2)

        c = ttk.LabelFrame(f, text="Converter", padding=6)
        c.pack(fill="x", pady=6)
        self.conv_var = tk.StringVar(value="generic")
        self.conv_combo = ttk.Combobox(c, textvariable=self.conv_var, values=list(self.convs), state="readonly", width=24)
        self.conv_combo.pack(side="left")
        self.conv_desc = ttk.Label(c, text="")
        self.conv_desc.pack(side="left", padx=8)
        self.conv_var.trace_add("write", lambda *_: self.conv_desc.config(
            text=getattr(self.convs.get(self.conv_var.get()), "DESCRIPTION", "")))
        self.conv_var.set(self.conv_var.get())

        t = ttk.LabelFrame(f, text="Where to put it (Apollo decrypted save folder)", padding=6)
        t.pack(fill="x")
        self.target_var = tk.StringVar()
        self.target_combo = ttk.Combobox(t, textvariable=self.target_var, width=80)
        self.target_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(t, text="Browse", command=self._pick_target).pack(side="left", padx=4)
        ttk.Button(t, text="New folder...", command=self._new_target).pack(side="left")

        ttk.Button(f, text="CONVERT", command=self._convert).pack(anchor="w", pady=8)
        self.log_box = tk.Text(f, height=14, wrap="word", state="disabled", bg="#111", fg="#ddd")
        self.log_box.pack(fill="both", expand=True)

    def _add_pc(self):
        for p in filedialog.askopenfilenames(title="Pick PC save file(s)"):
            p = Path(p)
            if p not in self.pc_files:
                self.pc_files.append(p)
                self.pc_list.insert("end", str(p))

    def _clear_pc(self):
        self.pc_files.clear()
        self.pc_list.delete(0, "end")

    def _game_ids(self) -> set[str]:
        g = self.game
        ids = {v["title_id"] for v in g.get("versions", [])} if g else set()
        if self.recommended:
            ids.add(self.recommended)
        return ids

    def _refresh_targets(self):
        # Only offer folders that belong to the selected game, so a save can't
        # land in another game's folder.
        ids = self._game_ids()
        mine = [s for s in self.usb_found if s.title_id in ids]
        vals = [str(s.path) for s in mine if s.kind == "decrypted"]
        self.target_combo["values"] = vals
        cur = self.target_var.get()
        if cur not in vals:
            self.target_var.set(vals[0] if vals else "")
        for s in mine:
            if s.kind == "empty":
                self.log(f"WARNING: {s.path.name} is EMPTY. That Apollo export didn't finish. "
                         "Export it again.")
        if self.usb_found and not vals:
            self.log(f"No decrypted export for this game ({', '.join(sorted(ids)) or 'no IDs'}) on the USB. "
                     "In Apollo: open the save > 'Export decrypted save files' > USB, then Scan USB again.")

    def _pick_target(self):
        d = filedialog.askdirectory(title="Pick the folder Apollo exported the decrypted save to")
        if d:
            self.target_var.set(d)

    def _new_target(self):
        tid = self.recommended
        if not tid:
            messagebox.showwarning("No version", "Run 'Recommend version' on the Version tab first.")
            return
        base = filedialog.askdirectory(title="Pick the USB drive root")
        if not base:
            return
        # Best guess at Apollo's layout. Exporting a real save first is safer.
        target = Path(base) / "PS4" / "APOLLO" / tid / "SAVEDATA00"
        self.target_var.set(str(target))
        messagebox.showinfo("New folder", f"Will create:\n{target}\n\nThis is a guess at Apollo's layout and "
                            "save folder name. Exporting a real save with Apollo first and picking that folder "
                            "is much more reliable.")

    def _convert(self):
        g = self.game
        if not g:
            return messagebox.showwarning("No game", "Pick a game on the Game tab.")
        if not self.pc_files:
            return messagebox.showwarning("No files", "Add your PC save file(s).")
        target = self.target_var.get().strip()
        if not target:
            return messagebox.showwarning("No target", "Pick where to put the converted save.")
        conv = self.convs.get(self.conv_var.get())
        if not conv:
            return messagebox.showerror("Converter", f"Converter '{self.conv_var.get()}' not found.")

        target = Path(target)
        existing = next((s for s in self.usb_found if s.path == target), None)
        tid_in_path = core.TITLE_ID_RE.search(target.name.upper()) or core.TITLE_ID_RE.search(str(target).upper())
        ids = self._game_ids()
        if tid_in_path and ids and tid_in_path.group(0) not in ids:
            return messagebox.showerror(
                "Wrong game's folder",
                f"That folder belongs to {tid_in_path.group(0)}, which isn't {g['name']} "
                f"({', '.join(sorted(ids))}).\n\nPick the Kakarot export folder, e.g. "
                f"..._{sorted(ids)[0]}_ManualSave1.")
        if not tid_in_path:
            if not messagebox.askyesno("No title ID", "The folder name has no title ID in it, so I can't "
                                       "check it's the right game. Continue anyway?"):
                return
        if target.exists() and not any(p.is_file() for p in target.iterdir()):
            if not messagebox.askyesno("Empty folder", "That folder is empty. The Apollo export probably "
                                       "failed, and importing from it may do nothing. Continue anyway?"):
                return

        self.log(f"=== Converting {g['name']} with '{conv.NAME}' ===")
        stage = Path(tempfile.mkdtemp(prefix="pssave_"))
        try:
            staged = conv.convert(self.pc_files, stage, g, self.log)
            res = core.package_into(staged, target, existing)
            if res.backup:
                self.log(f"Backed up the console's original files to: {res.backup}")
            self.log(f"Wrote {len(res.written)} file(s) to: {res.target}")
            for w in res.warnings:
                prefix = "" if w.startswith(("KEY CHECK", "NOTE:", "Renamed")) else "WARNING: "
                self.log(prefix + w)
            if (res.target / "sce_sys").is_dir():
                self.log("Done. This is a full save copy on the USB. On the PS4: Apollo > USB Saves > "
                         "this save > 'Copy save game' > 'Copy to HDD' (overwrite: yes). "
                         "Don't use 'Import decrypted' on it: that only edits the USB copy.\n")
            else:
                self.log("Done. On the PS4: Apollo > HDD Saves > this save > 'Import decrypted save files'.\n")
        except Exception as e:
            self.log("ERROR: " + "".join(traceback.format_exception_only(type(e), e)).strip())
            self.log(traceback.format_exc())
        finally:
            shutil.rmtree(stage, ignore_errors=True)

    # ------------------------------------------------------------- tab 4
    def _build_help_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="Help")
        t = tk.Text(f, wrap="word")
        t.pack(fill="both", expand=True)
        t.insert("1.0", HELP_TEXT)
        t.config(state="disabled")


class GameDialog(tk.Toplevel):
    """Add / edit a game entry."""

    def __init__(self, app: App, game: dict | None):
        super().__init__(app)
        self.app, self.game = app, game
        self.title("Edit game" if game else "Add game")
        self.geometry("620x560")
        self.transient(app)
        g = game or {}
        f = ttk.Frame(self, padding=10)
        f.pack(fill="both", expand=True)

        def row(label, r):
            ttk.Label(f, text=label).grid(row=r, column=0, sticky="nw", pady=3)

        self.name = ttk.Entry(f, width=50)
        self.name.insert(0, g.get("name", ""))
        row("Name", 0); self.name.grid(row=0, column=1, sticky="we")
        self.aliases = ttk.Entry(f, width=50)
        self.aliases.insert(0, ", ".join(g.get("aliases", [])))
        row("Aliases (comma sep.)", 1); self.aliases.grid(row=1, column=1, sticky="we")
        self.conv = ttk.Combobox(f, values=list(app.convs), state="readonly")
        self.conv.set(g.get("converter", "generic"))
        row("Converter", 2); self.conv.grid(row=2, column=1, sticky="w")
        self.hint = ttk.Entry(f, width=50)
        self.hint.insert(0, g.get("pc_save_hint", ""))
        row("PC save location", 3); self.hint.grid(row=3, column=1, sticky="we")

        row("Versions\n(one per line:\nTITLEID REGION EDITION)", 4)
        self.versions = tk.Text(f, height=7, width=50)
        self.versions.insert("1.0", "\n".join(
            f"{v['title_id']} {v.get('region', '')} {v.get('edition', '')}".strip()
            for v in g.get("versions", [])))
        self.versions.grid(row=4, column=1, sticky="we")
        row("Rename map\n(pc_pattern = ps4_name)", 5)
        self.fmap = tk.Text(f, height=4, width=50)
        self.fmap.insert("1.0", "\n".join(f"{k} = {v}" for k, v in g.get("file_map", {}).items()))
        self.fmap.grid(row=5, column=1, sticky="we")
        row("Notes", 6)
        self.notes = tk.Text(f, height=4, width=50, wrap="word")
        self.notes.insert("1.0", g.get("notes", ""))
        self.notes.grid(row=6, column=1, sticky="we")
        self.verified = tk.BooleanVar(value=all(v.get("verified") for v in g.get("versions", [])) and bool(g))
        ttk.Checkbutton(f, text="I've confirmed these title IDs on my console", variable=self.verified).grid(row=7, column=1, sticky="w")
        ttk.Button(f, text="Save", command=self._save).grid(row=8, column=1, sticky="e", pady=8)
        f.columnconfigure(1, weight=1)

    def _save(self):
        name = self.name.get().strip()
        if not name:
            return messagebox.showwarning("Name", "Enter a name.", parent=self)
        versions = []
        for line in self.versions.get("1.0", "end").splitlines():
            parts = line.split()
            if not parts:
                continue
            tid = core.normalize_title_id(parts[0])
            if not tid:
                return messagebox.showwarning("Title ID", f"Bad title ID: {parts[0]}", parent=self)
            versions.append({"title_id": tid, "platform": core.platform_of(tid),
                             "region": parts[1] if len(parts) > 1 else "",
                             "edition": " ".join(parts[2:]) if len(parts) > 2 else "",
                             "verified": self.verified.get()})
        fmap = {}
        for line in self.fmap.get("1.0", "end").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                fmap[k.strip()] = v.strip()
        entry = {"name": name,
                 "aliases": [a.strip() for a in self.aliases.get().split(",") if a.strip()],
                 "pc_save_hint": self.hint.get().strip(),
                 "converter": self.conv.get() or "generic",
                 "file_map": fmap,
                 "notes": self.notes.get("1.0", "end").strip(),
                 "versions": versions}
        games = self.app.db["games"]
        if self.game in games:
            idx = games.index(self.game)
            games[idx] = entry
        else:
            games.append(entry)
            idx = len(games) - 1
        core.save_db(self.app.db)
        self.app._refresh_games(select=idx)
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
