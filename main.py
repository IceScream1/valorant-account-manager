"""
╔══════════════════════════════════════════════════════════════════╗
║  VALORANT ACCOUNT MANAGER  v5                                   ║
║  ─────────────────────────────────────────────────────────────── ║
║  Smart clipboard · Session switching · Auto-launch toggle        ║
║  Dual themes · Nicknames · Auto-backups                          ║
║  Windows 10/11 · Python 3.10+ · No external dependencies        ║
╚══════════════════════════════════════════════════════════════════╝

CLICK FLOW:
  1. Click account → username on clipboard instantly (smart clipboard)
  2. Ctrl+V → pastes username, clipboard swaps to password
  3. Ctrl+V → pastes password, clipboard clears, status bar disappears

SESSION SWITCH FLOW:
  Click "⇄ Switch" on an account that has a saved session:
  1. Closes Riot Client (required — files are locked while running)
  2. Saves current session for the active account
  3. Restores target account's session
  4. Relaunches Riot Client (if auto-launch is on)
  → Riot auto-logs in with the restored session, no credentials needed

SAVE SESSION:
  Click "💾 Save" while logged into an account in Riot:
  → Snapshots the full Riot Client Data folder for that account
  → Only needs to be done once per account (after first manual login)
"""

import os
import sys
import json
import uuid
import time
import shutil
import ctypes
import ctypes.wintypes
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable
import tkinter as tk
from tkinter import messagebox


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  THEMES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

THEMES = {
    "valorant": {
        "name": "Valorant",
        "bg0": "#0f1115",  "bg1": "#171a21",  "bg2": "#1e2128",
        "bg3": "#272b33",  "bg4": "#2f343d",
        "accent": "#ff4655", "accent_h": "#ff6673", "accent_d": "#b8323d",
        "gold": "#e8c36e", "gold_d": "#a88a3e", "gold_bg": "#2a2518",
        "fav_hover": "#33301e",
        "green": "#3dd68c", "green_bg": "#1a3328",
        "blue": "#5ea7e8", "orange": "#e89b5e", "danger": "#e85e5e",
        "t1": "#e6e1d6", "t2": "#9ba1a6", "t3": "#5a5f66",
        "b1": "#2a2e36", "b2": "#383d47",
        "tog_on": "#3dd68c", "tog_off": "#5a5f66",
    },
    "cozy": {
        "name": "Cozy",
        "bg0": "#1c1714",  "bg1": "#241f1b",  "bg2": "#2e2722",
        "bg3": "#3a322c",  "bg4": "#453c35",
        "accent": "#d4896a", "accent_h": "#e0a084", "accent_d": "#a66248",
        "gold": "#c4a7d7", "gold_d": "#8e6fa8", "gold_bg": "#2a2430",
        "fav_hover": "#342d3a",
        "green": "#8cc084", "green_bg": "#223028",
        "blue": "#7db4c9", "orange": "#d4a96a", "danger": "#c97d7d",
        "t1": "#ede4d4", "t2": "#a89e90", "t3": "#6e655c",
        "b1": "#3a322c", "b2": "#4a413a",
        "tog_on": "#8cc084", "tog_off": "#6e655c",
    },
}

T: dict = {}
FONT = "Segoe UI"

def _apply_theme(name: str):
    T.clear()
    T.update(THEMES.get(name, THEMES["valorant"]))

_apply_theme("valorant")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONSTANTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RIOT_DATA_REL = r"Riot Games\Riot Client\Data"
RIOT_CLIENT_PATHS = [
    r"C:\Riot Games\Riot Client\RiotClientServices.exe",
    r"D:\Riot Games\Riot Client\RiotClientServices.exe",
    r"C:\Program Files\Riot Games\Riot Client\RiotClientServices.exe",
    r"C:\Program Files (x86)\Riot Games\Riot Client\RiotClientServices.exe",
]
RIOT_PROCESSES = [
    "RiotClientServices.exe", "Riot Client.exe", "RiotClientUx.exe",
    "RiotClientUxRender.exe", "VALORANT.exe", "vgtray.exe",
]
BACKUP_MAX = 30
VK_CONTROL = 0x11
VK_V       = 0x56


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PLATFORM HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _documents() -> Path:
    try:
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)
        return Path(buf.value)
    except Exception:
        return Path.home() / "Documents"

def _localappdata() -> Path:
    v = os.environ.get("LOCALAPPDATA", "")
    return Path(v) if v else Path.home() / "AppData" / "Local"

def _riot_data_dir() -> Path:
    return _localappdata() / RIOT_DATA_REL

def _kill_riot():
    """Close all Riot processes. Required before swapping session files."""
    no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    for name in RIOT_PROCESSES:
        try:
            subprocess.run(["taskkill", "/F", "/IM", name],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           creationflags=no_win)
        except Exception:
            pass

def _is_riot_running() -> bool:
    no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    try:
        out = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"],
            creationflags=no_win, stderr=subprocess.DEVNULL
        ).decode("utf-8", errors="ignore").lower()
        for n in ["riotclientservices.exe", "riotclientux.exe"]:
            if n in out:
                return True
    except Exception:
        pass
    return False

def _launch_riot(open_game=False) -> bool:
    args = ["--launch-product=valorant", "--launch-patchline=live"] if open_game else []
    for p in RIOT_CLIENT_PATHS:
        if os.path.isfile(p):
            try:
                subprocess.Popen(
                    [p] + args,
                    creationflags=subprocess.DETACHED_PROCESS
                        | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
                return True
            except Exception:
                continue
    try:
        os.startfile("riotclient:")
        return True
    except Exception:
        return False

def _dark_titlebar(root: tk.Tk):
    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)
    except Exception:
        pass

def _dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_DEF = {
    "session_switching": True,
    "auto_launch": True,
    "auto_backup": True,
    "backup_interval_min": 15,
    "sort_by_recent": True,
    "close_guard": True,
    "theme": "valorant",
    "geometry": "",
    "active_account": "",
}

def _new_account(nickname="", username="", password="", **kw) -> dict:
    a = {"id": str(uuid.uuid4())[:8], "nickname": nickname,
         "username": username, "password": password,
         "favorite": False, "use_count": 0, "last_used": None,
         "notes": "", "created": datetime.now().isoformat()}
    a.update(kw)
    return a


class Config:
    def __init__(self):
        self.dir = _documents() / "ValorantAccountManager"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "accounts.json"
        self.backup_dir = self.dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        self.session_dir = self.dir / "sessions"
        self.session_dir.mkdir(exist_ok=True)
        self._d: dict = {"accounts": [], "settings": dict(_DEF)}
        self._load()

    def _load(self):
        if not self.path.exists():
            self._save(); return
        try:
            raw = json.loads(self.path.read_text("utf-8"))
            self._d["accounts"] = raw.get("accounts", [])
            for a in self._d["accounts"]:
                if "nickname" not in a:
                    a["nickname"] = a.get("username", "Account")
            m = dict(_DEF); m.update(raw.get("settings", {}))
            self._d["settings"] = m
        except Exception:
            self._d = {"accounts": [], "settings": dict(_DEF)}

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._d, indent=2, ensure_ascii=False), "utf-8")
        tmp.replace(self.path)

    def save(self): self._save()
    def get(self, k, d=None): return self._d["settings"].get(k, d)
    def set(self, k, v): self._d["settings"][k] = v; self._save()

    @property
    def accounts(self): return self._d["accounts"]

    def add(self, a): self._d["accounts"].append(a); self._save()
    def remove(self, aid):
        self._d["accounts"] = [a for a in self.accounts if a["id"] != aid]
        self._save()
    def find(self, aid):
        return next((a for a in self.accounts if a["id"] == aid), None)
    def update(self, aid, p):
        a = self.find(aid)
        if a: a.update(p); self._save()
    def mark_used(self, aid):
        a = self.find(aid)
        if a:
            a["use_count"] = a.get("use_count", 0) + 1
            a["last_used"] = datetime.now().isoformat()
            self._save()

    def sorted_accounts(self):
        def ts(a):
            lu = a.get("last_used")
            if lu and self.get("sort_by_recent", True):
                try: return datetime.fromisoformat(lu).timestamp()
                except: pass
            return 0
        f = sorted([a for a in self.accounts if a.get("favorite")], key=ts, reverse=True)
        r = sorted([a for a in self.accounts if not a.get("favorite")], key=ts, reverse=True)
        return f + r

    def create_backup(self, label="auto"):
        if not self.path.exists(): return
        dest = self.backup_dir / f"{label}_{datetime.now():%Y%m%d_%H%M%S}.json"
        shutil.copy2(self.path, dest); self._prune()

    def _prune(self):
        fs = sorted(self.backup_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        while len(fs) > BACKUP_MAX: fs.pop(0).unlink(missing_ok=True)

    def list_backups(self):
        return [{"path": str(p), "name": p.stem,
            "time": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d  %H:%M"),
            "size_kb": round(p.stat().st_size / 1024, 1)}
            for p in sorted(self.backup_dir.glob("*.json"),
                            key=lambda x: x.stat().st_mtime, reverse=True)]

    def restore_backup(self, path):
        self.create_backup("pre-restore")
        shutil.copy2(path, self.path); self._load()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SESSION MANAGER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Sessions:
    """
    save(aid)  — copy current Riot Data/ → sessions/<aid>/
    restore(aid) — copy sessions/<aid>/ → Riot Data/
    switch(from, to) — save from → kill Riot → restore to
    """
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def _dir(self, aid: str) -> Path:
        d = self.cfg.session_dir / aid
        d.mkdir(parents=True, exist_ok=True)
        return d

    def has(self, aid: str) -> bool:
        d = self.cfg.session_dir / aid
        return d.exists() and any(d.iterdir()) if d.exists() else False

    def save(self, aid: str) -> bool:
        riot = _riot_data_dir()
        if not riot.exists():
            return False
        dest = self._dir(aid)
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        try:
            shutil.copytree(riot, dest, dirs_exist_ok=True)
            return True
        except Exception as e:
            print(f"[Session] Save error: {e}")
            return False

    def restore(self, aid: str) -> bool:
        src = self.cfg.session_dir / aid
        if not src.exists() or not any(src.iterdir()):
            return False
        riot = _riot_data_dir()
        if riot.exists():
            shutil.rmtree(riot, ignore_errors=True)
        try:
            riot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, riot, dirs_exist_ok=True)
            return True
        except Exception as e:
            print(f"[Session] Restore error: {e}")
            return False

    def switch(self, from_aid: Optional[str], to_aid: str) -> bool:
        """
        Full switch: save current → kill Riot → wait → restore target.
        Riot MUST be closed because it locks the Data folder files.
        """
        # 1) Save current account's session
        if from_aid:
            self.save(from_aid)

        # 2) Kill Riot (mandatory — files are locked while running)
        _kill_riot()
        # Wait for processes to fully die and release file locks
        for _ in range(20):  # up to 10 seconds
            time.sleep(0.5)
            if not _is_riot_running():
                break
        time.sleep(0.5)  # extra safety margin

        # 3) Restore target session
        return self.restore(to_aid)

    def delete(self, aid: str):
        d = self.cfg.session_dir / aid
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SMART CLIPBOARD
#  Click → username on clipboard → detect Ctrl+V → swap to password
#  → detect Ctrl+V → clear clipboard → done
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SmartClip:
    IDLE, PHASE_USER, PHASE_PASS = 0, 1, 2

    def __init__(self, root: tk.Tk, on_change: Callable):
        self.root = root
        self.on_change = on_change
        self.phase = self.IDLE
        self._u = self._p = ""
        self._polling = False
        self._prev = False

    @property
    def active(self): return self.phase != self.IDLE

    def start(self, user: str, pw: str):
        """Put username on clipboard and start monitoring for Ctrl+V."""
        # Cancel any existing sequence
        if self._polling:
            self._polling = False
            time.sleep(0.1)

        self._u, self._p = user, pw
        self.phase = self.PHASE_USER

        # Set clipboard on the main thread
        self._set_clipboard(user)
        self.on_change(self.phase)

        # Start keyboard monitor
        self._polling = True
        self._prev = False
        threading.Thread(target=self._poll, daemon=True).start()

    def cancel(self):
        self._polling = False
        self.phase = self.IDLE
        self._u = self._p = ""
        self.on_change(self.phase)

    def _set_clipboard(self, text: str):
        """Set clipboard contents. MUST be called from main thread."""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update_idletasks()
        except Exception as e:
            print(f"[Clip] Error: {e}")

    def _poll(self):
        """Background thread: poll for Ctrl+V via GetAsyncKeyState."""
        try:
            gaks = ctypes.windll.user32.GetAsyncKeyState
        except Exception:
            self._polling = False
            return

        while self._polling:
            ctrl = gaks(VK_CONTROL) & 0x8000
            v = gaks(VK_V) & 0x8000
            pressed = bool(ctrl and v)

            if pressed and not self._prev:
                # Ctrl+V was just pressed — wait a moment for paste to complete
                time.sleep(0.15)
                # Then handle on main thread
                self.root.after(0, self._handle_paste)

            self._prev = pressed
            time.sleep(0.04)

    def _handle_paste(self):
        """Called on main thread after Ctrl+V detected."""
        if self.phase == self.PHASE_USER:
            # Username was pasted. Now put password on clipboard.
            self.phase = self.PHASE_PASS
            self._set_clipboard(self._p)
            self.on_change(self.phase)

        elif self.phase == self.PHASE_PASS:
            # Password was pasted. Done — clear everything.
            self._polling = False
            self.phase = self.IDLE
            self._set_clipboard("")  # clear for security
            self._u = self._p = ""
            self.on_change(self.phase)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AUTO BACKUP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AutoBackup:
    def __init__(self, cfg):
        self.cfg = cfg; self._run = False
    def start(self):
        self._run = True
        threading.Thread(target=self._loop, daemon=True).start()
    def stop(self): self._run = False
    def _loop(self):
        while self._run:
            m = self.cfg.get("backup_interval_min", 15)
            for _ in range(int(m * 30)):
                if not self._run: return
                time.sleep(2)
            if self._run and self.cfg.get("auto_backup", True):
                self.cfg.create_backup("auto")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  WIDGETS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class FlatEntry(tk.Frame):
    def __init__(self, parent, label="", show=""):
        super().__init__(parent, bg=T["bg1"])
        self.var = tk.StringVar()
        if label:
            tk.Label(self, text=label, bg=T["bg1"], fg=T["t2"],
                     font=(FONT, 9)).pack(anchor="w", pady=(0, 3))
        fr = tk.Frame(self, bg=T["bg3"], highlightbackground=T["b1"],
                      highlightcolor=T["accent"], highlightthickness=1)
        fr.pack(fill="x")
        cfg = dict(bg=T["bg3"], fg=T["t1"], insertbackground=T["t1"],
                   font=(FONT, 11), relief="flat", bd=0)
        if show:
            cfg["show"] = show
        self.entry = tk.Entry(fr, textvariable=self.var, **cfg)
        self.entry.pack(fill="x", padx=8, pady=7)
    def get(self): return self.var.get().strip()
    def set(self, v): self.var.set(v)


class Btn(tk.Frame):
    """Button widget. Uses Frame+Canvas to avoid Python 3.13 crashes."""
    def __init__(self, parent, text, command=None,
                 bg_color=None, fg_color=None, hover_color=None,
                 btn_width=120, btn_height=34, font_size=10):
        try:
            pbg = parent.cget("bg")
        except Exception:
            pbg = T["bg1"]
        super().__init__(parent, bg=pbg)

        self._bg = bg_color or T["accent"]
        self._fg = fg_color or "#ffffff"
        self._hov_c = hover_color or T["accent_h"]
        self._cmd = command
        self._txt = text
        self.btn_w, self.btn_h, self._r = btn_width, btn_height, 6
        self._fs = font_size
        self._hov = False

        self._c = tk.Canvas(self, width=self.btn_w, height=self.btn_h,
                            bg=pbg, highlightthickness=0, bd=0)
        self._c.pack()
        self._draw()
        self._c.bind("<Enter>",    lambda e: self._sethov(True))
        self._c.bind("<Leave>",    lambda e: self._sethov(False))
        self._c.bind("<Button-1>", lambda e: self._cmd() if self._cmd else None)

    def _sethov(self, v):
        self._hov = v; self._draw()

    def _draw(self):
        c = self._c; c.delete("all")
        bg = self._hov_c if self._hov else self._bg
        r, w, h = self._r, self.btn_w, self.btn_h
        c.create_oval(0,0,2*r,2*r,fill=bg,outline=bg)
        c.create_oval(w-2*r,0,w,2*r,fill=bg,outline=bg)
        c.create_oval(0,h-2*r,2*r,h,fill=bg,outline=bg)
        c.create_oval(w-2*r,h-2*r,w,h,fill=bg,outline=bg)
        c.create_rectangle(r,0,w-r,h,fill=bg,outline=bg)
        c.create_rectangle(0,r,w,h-r,fill=bg,outline=bg)
        c.create_text(w//2,h//2,text=self._txt,fill=self._fg,
                      font=(FONT,self._fs,"bold"))


class Toggle(tk.Canvas):
    def __init__(self, parent, initial=False, command=None):
        try: pbg = parent.cget("bg")
        except Exception: pbg = T["bg1"]
        super().__init__(parent, width=44, height=24, bg=pbg,
                         highlightthickness=0, bd=0)
        self.on = initial; self._cmd = command; self._draw()
        self.bind("<Button-1>", self._toggle)

    def _toggle(self, e=None):
        self.on = not self.on; self._draw()
        if self._cmd: self._cmd(self.on)

    def _draw(self):
        self.delete("all")
        bg = T["tog_on"] if self.on else T["tog_off"]
        self.create_oval(0,0,24,24,fill=bg,outline=bg)
        self.create_oval(20,0,44,24,fill=bg,outline=bg)
        self.create_rectangle(12,0,32,24,fill=bg,outline=bg)
        kx = 26 if self.on else 5
        self.create_oval(kx,3,kx+18,21,fill="#fff",outline="#fff")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ACCOUNT CARD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AccountCard(tk.Frame):
    def __init__(self, parent, acc, has_session=False, is_active=False,
                 on_click=None, on_fav=None, on_edit=None,
                 on_delete=None, on_save=None, on_switch=None):
        fav = acc.get("favorite", False)
        bg = T["gold_bg"] if fav else T["bg2"]
        hbg = T["fav_hover"] if fav else T["bg3"]
        super().__init__(parent, bg=bg, cursor="hand2")

        self._acc = acc; self._on_click = on_click
        self._bg = bg; self._hbg = hbg

        # Left accent bar: green=active, gold=fav, gray=default
        bar_c = T["green"] if is_active else (T["gold"] if fav else T["b1"])
        tk.Frame(self, bg=bar_c, width=3).pack(side="left", fill="y")

        inner = tk.Frame(self, bg=bg, padx=14, pady=10)
        inner.pack(fill="both", expand=True)

        # Row 1: star + nickname + badges + actions
        r1 = tk.Frame(inner, bg=bg)
        r1.pack(fill="x")

        star = tk.Label(r1, text="\u2605" if fav else "\u2606", bg=bg,
                        fg=T["gold"] if fav else T["t3"],
                        font=(FONT, 14), cursor="hand2")
        star.pack(side="left", padx=(0, 10))
        star.bind("<Button-1>", lambda e: on_fav(acc["id"]) if on_fav else None)

        display = acc.get("nickname") or acc.get("username", "Account")
        nlbl = tk.Label(r1, text=display, bg=bg, fg=T["t1"],
                        font=(FONT, 12, "bold"), anchor="w")
        nlbl.pack(side="left")

        # Badges
        if is_active:
            tk.Label(r1, text=" \u25cf active", bg=bg, fg=T["green"],
                     font=(FONT, 8, "bold")).pack(side="left", padx=(6,0))
        if has_session:
            tk.Label(r1, text=" \u2713 session", bg=bg, fg=T["blue"],
                     font=(FONT, 8)).pack(side="left", padx=(6,0))

        # Actions (right)
        acts = tk.Frame(r1, bg=bg)
        acts.pack(side="right")

        def _mkbtn(parent, text, fg_c, cmd):
            l = tk.Label(parent, text=text, bg=bg, fg=fg_c,
                         font=(FONT, 9), cursor="hand2", padx=4)
            l.pack(side="left")
            l.bind("<Button-1>", lambda e: cmd())
            l.bind("<Enter>", lambda e: l.configure(fg=T["t1"]))
            l.bind("<Leave>", lambda e: l.configure(fg=fg_c))
            return l

        extra_labels = []

        # Switch button — only if account has a saved session
        if on_switch and has_session:
            extra_labels.append(
                _mkbtn(acts, "\u21c4 Switch", T["blue"],
                       lambda: on_switch(acc["id"])))

        # Save button
        if on_save:
            extra_labels.append(
                _mkbtn(acts, "\U0001f4be Save", T["green"],
                       lambda: on_save(acc["id"])))

        # Edit
        extra_labels.append(
            _mkbtn(acts, "\u270e", T["t2"],
                   lambda: on_edit(acc["id"]) if on_edit else None))

        # Delete
        dl = tk.Label(acts, text="\u2715", bg=bg, fg=T["t3"],
                      font=(FONT, 12), cursor="hand2", padx=4)
        dl.pack(side="left")
        dl.bind("<Button-1>", lambda e: on_delete(acc["id"]) if on_delete else None)
        dl.bind("<Enter>", lambda e: dl.configure(fg=T["danger"]))
        dl.bind("<Leave>", lambda e: dl.configure(fg=T["t3"]))

        # Row 2: subtitle
        parts = []
        if acc.get("last_used"):
            try:
                dt = datetime.fromisoformat(acc["last_used"])
                parts.append(f"Last: {dt.strftime('%b %d, %H:%M')}")
            except Exception: pass
        uc = acc.get("use_count", 0)
        if uc: parts.append(f"Logins: {uc}")
        if acc.get("notes"): parts.append(acc["notes"][:50])
        if parts:
            tk.Label(inner, text="  \u00b7  ".join(parts), bg=bg,
                     fg=T["t2"], font=(FONT, 9), anchor="w"
                     ).pack(anchor="w", padx=(28, 0))

        # Hover + click
        self._ws = [self, inner, r1, nlbl, star, acts, dl] + extra_labels
        for w in (self, inner, r1, nlbl):
            w.bind("<Button-1>", lambda e: self._click())
            w.bind("<Enter>", self._ent)
            w.bind("<Leave>", self._lve)

    def _click(self):
        if self._on_click: self._on_click(self._acc["id"])
    def _ent(self, e=None):
        for w in self._ws:
            try: w.configure(bg=self._hbg)
            except: pass
    def _lve(self, e=None):
        for w in self._ws:
            try: w.configure(bg=self._bg)
            except: pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DIALOGS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class _Dlg(tk.Toplevel):
    def __init__(self, parent, title, w=440, h=400):
        super().__init__(parent); self.title(title)
        self.configure(bg=T["bg1"]); self.resizable(False, False)
        self.transient(parent); self.grab_set(); self.result = None
        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width() - w) // 2
        py = parent.winfo_y() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{max(0,px)}+{max(0,py)}")


class AccountDialog(_Dlg):
    def __init__(self, parent, title="Add Account", acc=None):
        super().__init__(parent, title, 440, 440)
        acc = acc or {}
        self.f_nick = FlatEntry(self, "Nickname (display name \u2014 safe for stream)")
        self.f_nick.pack(fill="x", padx=24, pady=(20, 0))
        self.f_nick.set(acc.get("nickname", ""))
        self.f_user = FlatEntry(self, "Username / Email (hidden, for login only)")
        self.f_user.pack(fill="x", padx=24, pady=(12, 0))
        self.f_user.set(acc.get("username", ""))
        self.f_pass = FlatEntry(self, "Password", show="\u2022")
        self.f_pass.pack(fill="x", padx=24, pady=(12, 0))
        self.f_pass.set(acc.get("password", ""))
        self._show = tk.BooleanVar(value=False)
        tk.Checkbutton(self, text="Show password", variable=self._show,
                       bg=T["bg1"], fg=T["t3"], selectcolor=T["bg3"],
                       activebackground=T["bg1"], activeforeground=T["t2"],
                       font=(FONT, 9), command=self._tog
                       ).pack(anchor="w", padx=24, pady=(4, 0))
        self.f_notes = FlatEntry(self, "Notes (optional)")
        self.f_notes.pack(fill="x", padx=24, pady=(12, 0))
        self.f_notes.set(acc.get("notes", ""))
        self._fav = tk.BooleanVar(value=acc.get("favorite", False))
        tk.Checkbutton(self, text="\u2605  Favorite", variable=self._fav,
                       bg=T["bg1"], fg=T["gold"], selectcolor=T["bg3"],
                       activebackground=T["bg1"], activeforeground=T["gold"],
                       font=(FONT, 10, "bold")
                       ).pack(anchor="w", padx=24, pady=(14, 0))
        bf = tk.Frame(self, bg=T["bg1"])
        bf.pack(fill="x", padx=24, pady=(20, 20), side="bottom")
        Btn(bf, "Save", self._save, btn_width=100, btn_height=36).pack(side="right")
        Btn(bf, "Cancel", self.destroy, bg_color=T["bg4"], hover_color=T["b2"],
            fg_color=T["t2"], btn_width=90, btn_height=36
            ).pack(side="right", padx=(0, 10))
        self.f_nick.entry.focus_set()
        self.bind("<Return>", lambda e: self._save())

    def _tog(self):
        self.f_pass.entry.configure(show="" if self._show.get() else "\u2022")

    def _save(self):
        u, p = self.f_user.get(), self.f_pass.get()
        if not u or not p:
            messagebox.showwarning("Required", "Username and password required.", parent=self)
            return
        self.result = {"nickname": self.f_nick.get() or u, "username": u,
                       "password": p, "notes": self.f_notes.get(),
                       "favorite": self._fav.get()}
        self.destroy()


class SettingsDialog(_Dlg):
    def __init__(self, parent, cfg, on_theme):
        super().__init__(parent, "Settings", 500, 460)
        self.cfg = cfg; self._on_theme = on_theme
        tk.Label(self, text="Settings", bg=T["bg1"], fg=T["t1"],
                 font=(FONT, 16, "bold")).pack(anchor="w", padx=24, pady=(20,16))
        self._togs = {}
        for key, label in [
            ("session_switching", "Enable session switching"),
            ("auto_launch",      "Auto-launch Riot Client (visible in toolbar too)"),
            ("auto_backup",      "Automatic periodic backups"),
            ("sort_by_recent",   "Sort non-favorites by most recently used"),
            ("close_guard",      "Warn before closing during paste sequence"),
        ]:
            row = tk.Frame(self, bg=T["bg1"]); row.pack(fill="x", padx=24, pady=4)
            tk.Label(row, text=label, bg=T["bg1"], fg=T["t1"],
                     font=(FONT, 10)).pack(side="left", fill="x", expand=True)
            t = Toggle(row, initial=cfg.get(key, True))
            t.pack(side="right"); self._togs[key] = t

        tk.Frame(self, bg=T["b1"], height=1).pack(fill="x", padx=24, pady=10)
        iv = tk.Frame(self, bg=T["bg1"]); iv.pack(fill="x", padx=24)
        tk.Label(iv, text="Backup interval (minutes)", bg=T["bg1"],
                 fg=T["t2"], font=(FONT, 10)).pack(side="left")
        self._iv = tk.StringVar(value=str(cfg.get("backup_interval_min", 15)))
        tk.Entry(iv, textvariable=self._iv, width=6, bg=T["bg3"], fg=T["t1"],
                 insertbackground=T["t1"], font=(FONT, 11), relief="flat", bd=0,
                 highlightbackground=T["b1"], highlightthickness=1
                 ).pack(side="right", ipady=4, padx=4)

        tk.Frame(self, bg=T["b1"], height=1).pack(fill="x", padx=24, pady=10)
        tk.Label(self, text="Theme", bg=T["bg1"], fg=T["t1"],
                 font=(FONT, 11, "bold")).pack(anchor="w", padx=24)
        tf = tk.Frame(self, bg=T["bg1"]); tf.pack(fill="x", padx=24, pady=(4,0))
        self._tv = tk.StringVar(value=cfg.get("theme", "valorant"))
        for tid, td in THEMES.items():
            f = tk.Frame(tf, bg=T["bg1"]); f.pack(side="left", padx=(0, 20))
            tk.Radiobutton(f, text=td["name"], variable=self._tv, value=tid,
                           bg=T["bg1"], fg=T["t1"], selectcolor=T["bg3"],
                           activebackground=T["bg1"], activeforeground=T["t1"],
                           font=(FONT, 10)).pack(side="left")
            for c in [td["accent"], td["gold"], td["green"]]:
                tk.Frame(f, bg=c, width=10, height=10).pack(side="left", padx=1)

        bf = tk.Frame(self, bg=T["bg1"])
        bf.pack(fill="x", padx=24, pady=(16, 20), side="bottom")
        Btn(bf, "Save", self._save, btn_width=100, btn_height=36).pack(side="right")
        Btn(bf, "Cancel", self.destroy, bg_color=T["bg4"], hover_color=T["b2"],
            fg_color=T["t2"], btn_width=90, btn_height=36
            ).pack(side="right", padx=(0, 10))

    def _save(self):
        for k, t in self._togs.items(): self.cfg.set(k, t.on)
        try: self.cfg.set("backup_interval_min", max(1, int(self._iv.get())))
        except: pass
        new = self._tv.get(); old = self.cfg.get("theme", "valorant")
        self.cfg.set("theme", new); self.cfg.save()
        self.result = True; self.destroy()
        if new != old: self._on_theme(new)


class BackupDialog(_Dlg):
    def __init__(self, parent, cfg, on_restore):
        super().__init__(parent, "Backups", 540, 480)
        self.cfg = cfg; self._on_r = on_restore
        tk.Label(self, text="Backups", bg=T["bg1"], fg=T["t1"],
                 font=(FONT, 16, "bold")).pack(anchor="w", padx=24, pady=(20,2))
        tk.Label(self, text=str(cfg.backup_dir), bg=T["bg1"], fg=T["t3"],
                 font=(FONT, 8)).pack(anchor="w", padx=24, pady=(0,10))
        Btn(self, "Create Backup Now", self._man,
            btn_width=170, btn_height=32, font_size=9
            ).pack(anchor="w", padx=24, pady=(0,10))
        lf = tk.Frame(self, bg=T["bg1"])
        lf.pack(fill="both", expand=True, padx=24)
        self.lb = tk.Listbox(lf, bg=T["bg2"], fg=T["t1"],
            selectbackground=T["accent"], selectforeground="#fff",
            font=("Consolas", 9), relief="flat", bd=0,
            highlightthickness=1, highlightbackground=T["b1"], activestyle="none")
        sb = tk.Scrollbar(lf, orient="vertical", command=self.lb.yview)
        self.lb.configure(yscrollcommand=sb.set)
        self.lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y"); self._ref()
        bf = tk.Frame(self, bg=T["bg1"])
        bf.pack(fill="x", padx=24, pady=(10, 20))
        Btn(bf, "Restore Selected", self._rest, bg_color=T["orange"],
            hover_color="#ffb74d", btn_width=150, btn_height=34, font_size=9
            ).pack(side="right")
        Btn(bf, "Open Folder", self._opn, bg_color=T["bg4"],
            hover_color=T["b2"], fg_color=T["t2"],
            btn_width=110, btn_height=34, font_size=9
            ).pack(side="right", padx=(0, 8))

    def _ref(self):
        self.lb.delete(0, "end"); self._bk = self.cfg.list_backups()
        for b in self._bk:
            self.lb.insert("end", f"  {b['time']}   {b['name']:<30s}   {b['size_kb']} KB")
    def _man(self): self.cfg.create_backup("manual"); self._ref()
    def _opn(self):
        try: os.startfile(str(self.cfg.backup_dir))
        except: pass
    def _rest(self):
        sel = self.lb.curselection()
        if not sel or sel[0] >= len(self._bk): return
        b = self._bk[sel[0]]
        if messagebox.askyesno("Restore", f"Restore from {b['name']}?\nSafety backup first.", parent=self):
            self.cfg.restore_backup(b["path"]); self._on_r(); self._ref()
            messagebox.showinfo("Done", "Restored.", parent=self)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN APP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("VALORANT \u00b7 Account Manager")
        self.root.minsize(560, 400)

        self.cfg = Config()
        _apply_theme(self.cfg.get("theme", "valorant"))
        self.root.configure(bg=T["bg0"])

        self.sessions = Sessions(self.cfg)
        self.auto_bk = AutoBackup(self.cfg)
        self.clip = SmartClip(self.root, self._clip_state)
        self._dismiss_id = None

        self._search = tk.StringVar()
        self._search.trace_add("write", lambda *_: self._render())

        g = self.cfg.get("geometry", "")
        try: self.root.geometry(g if g else "660x720")
        except: self.root.geometry("660x720")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.update_idletasks()
        _dark_titlebar(self.root)

        self._build()
        self._render()
        self.auto_bk.start()

    def _rebuild_ui(self):
        for w in self.root.winfo_children(): w.destroy()
        self.root.configure(bg=T["bg0"])
        self._build(); self._render()

    def _on_theme_change(self, name):
        _apply_theme(name); self._rebuild_ui()

    # ── build ────────────────────────────────────────────────────────

    def _build(self):
        # TOP BAR
        self._topbar = tk.Frame(self.root, bg=T["bg1"], height=56)
        self._topbar.pack(fill="x"); self._topbar.pack_propagate(False)

        lf = tk.Frame(self._topbar, bg=T["bg1"])
        lf.pack(side="left", padx=16)
        tk.Label(lf, text="\u25c6", bg=T["bg1"], fg=T["accent"],
                 font=(FONT, 18)).pack(side="left")
        tk.Label(lf, text=" VALORANT", bg=T["bg1"], fg=T["t1"],
                 font=(FONT, 13, "bold")).pack(side="left")
        tk.Label(lf, text="  accounts", bg=T["bg1"], fg=T["t3"],
                 font=(FONT, 11)).pack(side="left")

        badge = tk.Label(lf, text=f"  {T['name']}", bg=T["bg1"],
                         fg=T["accent"], font=(FONT, 8, "bold"), cursor="hand2")
        badge.pack(side="left", padx=(8,0))
        badge.bind("<Button-1>", lambda e: self._quick_theme())

        # Right side of top bar: auto-launch toggle + settings + backups
        tr = tk.Frame(self._topbar, bg=T["bg1"])
        tr.pack(side="right", padx=12)

        # AUTO-LAUNCH TOGGLE (visible in toolbar)
        al_frame = tk.Frame(tr, bg=T["bg1"])
        al_frame.pack(side="left", padx=(0, 12))
        tk.Label(al_frame, text="Auto-launch", bg=T["bg1"], fg=T["t3"],
                 font=(FONT, 8)).pack(side="left", padx=(0, 4))
        self._al_toggle = Toggle(
            al_frame, initial=self.cfg.get("auto_launch", True),
            command=self._on_autolaunch_toggle)
        self._al_toggle.pack(side="left")

        Btn(tr, "\u2699", self._open_settings, bg_color=T["bg3"],
            hover_color=T["bg4"], fg_color=T["t2"],
            btn_width=36, btn_height=30, font_size=13).pack(side="left", padx=3)
        Btn(tr, "\U0001f4e6", self._open_backups, bg_color=T["bg3"],
            hover_color=T["bg4"], fg_color=T["t2"],
            btn_width=36, btn_height=30, font_size=11).pack(side="left", padx=3)

        # STATUS BAR (hidden by default)
        self._stat_f = tk.Frame(self.root, bg=T["accent"])
        self._stat_l = tk.Label(self._stat_f, text="", bg=T["accent"],
                                fg="#fff", font=(FONT, 10, "bold"),
                                pady=6, padx=12, anchor="w")
        self._stat_l.pack(fill="x")
        self._stat_vis = False

        # SEARCH + ADD
        bar = tk.Frame(self.root, bg=T["bg0"])
        bar.pack(fill="x", padx=16, pady=(12, 6))
        sf = tk.Frame(bar, bg=T["bg3"], highlightbackground=T["b1"],
                      highlightthickness=1)
        sf.pack(side="left", fill="x", expand=True)
        tk.Label(sf, text="\U0001f50d", bg=T["bg3"], fg=T["t3"],
                 font=(FONT, 11)).pack(side="left", padx=(10, 4))
        tk.Entry(sf, textvariable=self._search, bg=T["bg3"], fg=T["t1"],
                 insertbackground=T["t1"], font=(FONT, 11), relief="flat",
                 bd=0, highlightthickness=0
                 ).pack(side="left", fill="x", expand=True, padx=4, pady=8)
        Btn(bar, "+ Add", self._add, btn_width=80, btn_height=36
            ).pack(side="right", padx=(10, 0))

        # SCROLLABLE LIST
        lo = tk.Frame(self.root, bg=T["bg0"])
        lo.pack(fill="both", expand=True, padx=16, pady=(4, 0))
        self._cv = tk.Canvas(lo, bg=T["bg0"], highlightthickness=0, bd=0)
        self._scr = tk.Scrollbar(lo, orient="vertical", command=self._cv.yview)
        self._lf = tk.Frame(self._cv, bg=T["bg0"])
        self._lf.bind("<Configure>",
            lambda e: self._cv.configure(scrollregion=self._cv.bbox("all")))
        self._cw = self._cv.create_window((0,0), window=self._lf, anchor="nw")
        self._cv.bind("<Configure>",
            lambda e: self._cv.itemconfig(self._cw, width=e.width))
        self._cv.configure(yscrollcommand=self._scr.set)
        self._cv.pack(side="left", fill="both", expand=True)
        self._scr.pack(side="right", fill="y")
        self._cv.bind("<Enter>", lambda e: self._cv.bind_all(
            "<MouseWheel>", lambda ev: self._cv.yview_scroll(-ev.delta//120, "units")))
        self._cv.bind("<Leave>", lambda e: self._cv.unbind_all("<MouseWheel>"))

        # BOTTOM
        self._bot = tk.Label(self.root, text="", bg=T["bg0"], fg=T["t3"],
                             font=(FONT, 9), anchor="w", padx=16, pady=8)
        self._bot.pack(fill="x", side="bottom")

    def _on_autolaunch_toggle(self, val):
        self.cfg.set("auto_launch", val)

    # ── status bar ───────────────────────────────────────────────────

    def _show_status(self, text, color, dismiss_ms=0):
        if self._dismiss_id is not None:
            self.root.after_cancel(self._dismiss_id)
            self._dismiss_id = None
        self._stat_f.configure(bg=color)
        self._stat_l.configure(text=text, bg=color)
        if not self._stat_vis:
            self._stat_f.pack(fill="x", after=self._topbar)
            self._stat_vis = True
        if dismiss_ms > 0:
            self._dismiss_id = self.root.after(dismiss_ms, self._hide_status)

    def _hide_status(self):
        if self._dismiss_id is not None:
            self.root.after_cancel(self._dismiss_id)
            self._dismiss_id = None
        if self._stat_vis:
            self._stat_f.pack_forget()
            self._stat_vis = False

    def _quick_theme(self):
        keys = list(THEMES.keys())
        cur = self.cfg.get("theme", "valorant")
        idx = keys.index(cur) if cur in keys else 0
        self.cfg.set("theme", keys[(idx + 1) % len(keys)])
        self._on_theme_change(keys[(idx + 1) % len(keys)])

    # ── render ───────────────────────────────────────────────────────

    def _render(self):
        for w in self._lf.winfo_children(): w.destroy()
        accs = self.cfg.sorted_accounts()
        q = self._search.get().strip().lower()
        if q:
            accs = [a for a in accs
                    if q in (a.get("nickname") or "").lower()
                    or q in a.get("username", "").lower()
                    or q in a.get("notes", "").lower()]

        ses_on = self.cfg.get("session_switching", True)
        active_id = self.cfg.get("active_account", "")

        if not accs:
            ef = tk.Frame(self._lf, bg=T["bg0"])
            ef.pack(fill="x", pady=50)
            tk.Label(ef, text="No accounts yet" if not q else "No matches",
                     bg=T["bg0"], fg=T["t3"], font=(FONT, 14)).pack()
            if not q:
                tk.Label(ef, text='Click "+ Add" to get started',
                         bg=T["bg0"], fg=T["t3"], font=(FONT, 10)).pack(pady=(6,0))
            self._bot.configure(text=""); return

        has_fav = any(a.get("favorite") for a in accs)
        fav_hdr = other_hdr = False

        for acc in accs:
            fav = acc.get("favorite", False)
            if has_fav and fav and not fav_hdr:
                fav_hdr = True
                tk.Label(self._lf, text="FAVORITES", bg=T["bg0"],
                         fg=T["gold_d"], font=(FONT, 9, "bold"),
                         anchor="w").pack(fill="x", padx=4, pady=(10,4))
            if has_fav and not fav and not other_hdr:
                other_hdr = True
                tk.Frame(self._lf, bg=T["b1"], height=1).pack(fill="x", padx=4, pady=(12,2))
                tk.Label(self._lf, text="ALL ACCOUNTS", bg=T["bg0"],
                         fg=T["t3"], font=(FONT, 9, "bold"),
                         anchor="w").pack(fill="x", padx=4, pady=(4,4))

            has_ses = self.sessions.has(acc["id"]) if ses_on else False
            is_act = acc["id"] == active_id

            AccountCard(
                self._lf, acc, has_session=has_ses, is_active=is_act,
                on_click=self._on_click,
                on_fav=self._toggle_fav,
                on_edit=self._edit,
                on_delete=self._delete,
                on_save=self._save_session if ses_on else None,
                on_switch=self._switch_session if ses_on else None,
            ).pack(fill="x", pady=2)

        total = len(self.cfg.accounts)
        favs = sum(1 for a in self.cfg.accounts if a.get("favorite"))
        self._bot.configure(
            text=f"{total} account{'s' if total != 1 else ''}   \u00b7   "
                 f"{favs} favorite{'s' if favs != 1 else ''}")

    # ──────────────────────────────────────────────────────────────────
    #  CLICK ACCOUNT  →  copy credentials (always works, instantly)
    # ──────────────────────────────────────────────────────────────────

    def _on_click(self, aid):
        """Click account = copy username to clipboard + start smart paste."""
        acc = self.cfg.find(aid)
        if not acc: return
        self.cfg.mark_used(aid)
        self.cfg.set("active_account", aid)

        # START SMART CLIPBOARD — this is instant and always works
        self.clip.start(acc["username"], acc["password"])

        # Also launch Riot if the toggle is on
        if self.cfg.get("auto_launch", True):
            _launch_riot(open_game=False)

        self._render()

    # ──────────────────────────────────────────────────────────────────
    #  SWITCH SESSION  →  close Riot → swap Data folder → relaunch
    # ──────────────────────────────────────────────────────────────────

    def _switch_session(self, aid):
        acc = self.cfg.find(aid)
        if not acc: return
        display = acc.get("nickname") or "?"
        active_id = self.cfg.get("active_account", "")

        msg = (f'Switch session to "{display}"?\n\n'
               "\u2022  Riot Client will be closed (required to swap files)\n"
               "\u2022  Current session saved for the active account\n"
               "\u2022  Target session restored\n")
        if self.cfg.get("auto_launch", True):
            msg += "\u2022  Riot Client will relaunch automatically"

        if not messagebox.askyesno("Switch Session", msg, parent=self.root):
            return

        self._show_status(f"  \U0001f504  Switching to {display}...", T["accent"])

        def _do():
            # switch() internally: save current → kill Riot → wait → restore target
            ok = self.sessions.switch(active_id if active_id else None, aid)
            self.cfg.set("active_account", aid)

            if ok and self.cfg.get("auto_launch", True):
                _launch_riot(open_game=True)

            self.root.after(0, self._render)
            if ok:
                self.root.after(0, lambda: self._show_status(
                    f"  \u2713  Switched to {display}",
                    T["green_bg"], dismiss_ms=4000))
            else:
                self.root.after(0, lambda: self._show_status(
                    f"  \u26a0  Switch to {display} \u2014 no saved session found",
                    T["orange"], dismiss_ms=4000))

        threading.Thread(target=_do, daemon=True).start()

    # ──────────────────────────────────────────────────────────────────
    #  SAVE SESSION  →  snapshot current Riot Data for this account
    # ──────────────────────────────────────────────────────────────────

    def _save_session(self, aid):
        acc = self.cfg.find(aid)
        if not acc: return
        display = acc.get("nickname") or "?"

        if not _riot_data_dir().exists():
            messagebox.showwarning("No Data",
                "Riot Client Data folder not found.\n\n"
                "Log in to this account in Riot first,\n"
                "then click Save to capture the session.",
                parent=self.root)
            return

        if not messagebox.askyesno("Save Session",
                f'Save login session for "{display}"?\n\n'
                "Make sure you are currently logged into\n"
                "this account in the Riot Client.",
                parent=self.root):
            return

        self._show_status(f"  \U0001f4be  Saving session for {display}...", T["accent"])

        def _do():
            ok = self.sessions.save(aid)
            if ok: self.cfg.set("active_account", aid)
            self.root.after(0, self._render)
            if ok:
                self.root.after(0, lambda: self._show_status(
                    f"  \u2713  Session saved for {display}",
                    T["green_bg"], dismiss_ms=3000))
            else:
                self.root.after(0, self._hide_status)
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", "Failed to save session.", parent=self.root))

        threading.Thread(target=_do, daemon=True).start()

    # ── other actions ────────────────────────────────────────────────

    def _toggle_fav(self, aid):
        a = self.cfg.find(aid)
        if a:
            self.cfg.update(aid, {"favorite": not a.get("favorite", False)})
            self._render()

    def _add(self):
        d = AccountDialog(self.root)
        self.root.wait_window(d)
        if d.result:
            self.cfg.add(_new_account(**d.result)); self._render()

    def _edit(self, aid):
        a = self.cfg.find(aid)
        if not a: return
        d = AccountDialog(self.root, "Edit Account", a)
        self.root.wait_window(d)
        if d.result: self.cfg.update(aid, d.result); self._render()

    def _delete(self, aid):
        a = self.cfg.find(aid)
        if not a: return
        display = a.get("nickname") or "?"
        if messagebox.askyesno("Delete", f'Delete "{display}"?\nCannot be undone.',
                               parent=self.root):
            self.sessions.delete(aid)
            if self.cfg.get("active_account") == aid:
                self.cfg.set("active_account", "")
            self.cfg.remove(aid); self._render()

    # ── clipboard status bar ─────────────────────────────────────────

    def _clip_state(self, phase):
        if phase == SmartClip.PHASE_USER:
            self._show_status(
                "  \U0001f4cb  USERNAME copied  \u2014  "
                "press Ctrl+V in Riot  \u2192  password next",
                T["accent"])
        elif phase == SmartClip.PHASE_PASS:
            self._show_status(
                "  \U0001f511  PASSWORD copied  \u2014  "
                "press Ctrl+V  \u2192  done",
                T["green_bg"])
        elif phase == SmartClip.IDLE:
            self._hide_status()

    # ── dialogs ──────────────────────────────────────────────────────

    def _open_settings(self):
        d = SettingsDialog(self.root, self.cfg, self._on_theme_change)
        self.root.wait_window(d)
        if d.result:
            # Sync the toolbar toggle with settings
            self._al_toggle.on = self.cfg.get("auto_launch", True)
            self._al_toggle._draw()
            self._render()

    def _open_backups(self):
        BackupDialog(self.root, self.cfg, on_restore=self._render)

    # ── close guard ──────────────────────────────────────────────────

    def _on_close(self):
        if self.clip.active and self.cfg.get("close_guard", True):
            ans = messagebox.askyesnocancel(
                "Paste In Progress",
                "A paste sequence is active!\n\n"
                "Yes \u2192 close anyway\n"
                "No \u2192 cancel paste, then close\n"
                "Cancel \u2192 go back", parent=self.root)
            if ans is None: return
            if ans is False: self.clip.cancel()
        elif self.clip.active:
            self.clip.cancel()

        self.cfg.set("geometry", self.root.geometry())
        self.cfg.save(); self.auto_bk.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    _dpi_aware()
    App().run()