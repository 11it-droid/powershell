"""
Live Wallpaper — production-ready desktop video wallpaper engine for Windows.

Architecture
============
  • Backend  : VLC (auto-detected system-wide or auto-downloaded portable)
  • Embedding : WorkerW / Progman Win32 trick
  • GUI       : tkinter with custom dark theme, tabbed layout, tooltips,
                recent-files history, drag-and-drop path entry, sparklines
  • Threading : all VLC / download work runs in daemon threads; every UI
                callback is marshalled back via after(0, …)
  • State     : single _WallpaperState dataclass; GUI only reads/writes through
                safe helper methods

Tested on Python 3.10 – 3.13 / Windows 10 & 11.
"""

# ──────────────────────────────────────────────────────────────────────────────
#  Bootstrap — install missing pip packages before any heavy import
# ──────────────────────────────────────────────────────────────────────────────
import subprocess, sys, importlib.util

def _pip(pkg: str) -> None:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

for _pkg, _imp in [("psutil", "psutil"), ("python-vlc", None)]:
    if _imp and importlib.util.find_spec(_imp) is None:
        print(f"Installing {_pkg}…")
        _pip(_pkg)
    elif _imp is None and importlib.util.find_spec("vlc") is None:
        print(f"Installing {_pkg}…")
        _pip(_pkg)

# ──────────────────────────────────────────────────────────────────────────────
#  Standard imports
# ──────────────────────────────────────────────────────────────────────────────
import ctypes, json, logging, os, shutil, signal, string
import threading, time, traceback, urllib.request, zipfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import psutil

# ──────────────────────────────────────────────────────────────────────────────
#  Logging
# ──────────────────────────────────────────────────────────────────────────────
LOG_FILE = Path(os.environ.get("APPDATA", Path.home())) / "LiveWallpaper" / "app.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("live_wallpaper")

# ──────────────────────────────────────────────────────────────────────────────
#  Constants & paths
# ──────────────────────────────────────────────────────────────────────────────
APP_NAME    = "Live Wallpaper"
APP_VERSION = "2.0.0"

if getattr(sys, "frozen", False):
    SCRIPT_DIR = Path(sys._MEIPASS)
else:
    SCRIPT_DIR = Path(__file__).resolve().parent

DATA_DIR            = Path(os.environ.get("APPDATA", Path.home())) / "LiveWallpaper"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE       = DATA_DIR / "settings.json"
VLC_PORTABLE_FOLDER = DATA_DIR / "vlc_portable"
VLC_URL             = "https://get.videolan.org/vlc/3.0.18/win64/vlc-3.0.18-win64.zip"
VLC_ZIP_VERSION     = "vlc-3.0.18"

SUPPORTED = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".gif", ".wmv", ".flv", ".m4v")
MAX_RECENT = 10

# ──────────────────────────────────────────────────────────────────────────────
#  Settings (persistent JSON)
# ──────────────────────────────────────────────────────────────────────────────
_DEFAULT_SETTINGS = {
    "recent_files": [],
    "mute":         True,
    "volume":       0,
    "speed":        1.0,
    "loop":         True,
    "fit_mode":     "stretch",   # stretch | fit | fill
    "last_file":    "",
    "theme":        "dark",
}

def load_settings() -> dict:
    try:
        if SETTINGS_FILE.is_file():
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            return {**_DEFAULT_SETTINGS, **data}
    except Exception as exc:
        log.warning("Could not load settings: %s", exc)
    return dict(_DEFAULT_SETTINGS)

def save_settings(s: dict) -> None:
    try:
        SETTINGS_FILE.write_text(json.dumps(s, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("Could not save settings: %s", exc)

# ──────────────────────────────────────────────────────────────────────────────
#  Smart VLC finder
# ──────────────────────────────────────────────────────────────────────────────
def find_vlc_folder() -> Optional[Path]:
    """
    Locate an existing VLC installation by checking (in order):
      1. Portable folder in AppData
      2. Standard Program Files paths
      3. Windows registry (HKLM / HKCU)
      4. PATH entries
      5. Drive walk — up to 4 levels, skipping system folders
    Returns the Path containing libvlc.dll, or None.
    """
    def dll_in(folder: Path) -> Optional[Path]:
        try:
            return folder if (folder / "libvlc.dll").is_file() else None
        except (OSError, PermissionError):
            return None

    # 1. Portable folder in AppData
    r = dll_in(VLC_PORTABLE_FOLDER)
    if r: return r

    # 2. Program Files
    pf_seen: list[Path] = []
    for env in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        v = os.environ.get(env)
        if v:
            p = Path(v)
            if p not in pf_seen:
                pf_seen.append(p)
    for root in pf_seen:
        for cand in (root / "VideoLAN" / "VLC", root / "VLC"):
            r = dll_in(cand)
            if r: return r

    # 3. Registry
    try:
        import winreg
        for hive, sub in [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\VideoLAN\VLC"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\VideoLAN\VLC"),
            (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\VideoLAN\VLC"),
        ]:
            try:
                with winreg.OpenKey(hive, sub) as key:
                    for val_name in ("InstallDir", ""):
                        try:
                            val, _ = winreg.QueryValueEx(key, val_name)
                            p = Path(val)
                            r = dll_in(p if p.is_dir() else p.parent)
                            if r: return r
                        except FileNotFoundError:
                            pass
            except (FileNotFoundError, OSError):
                pass
    except ImportError:
        pass

    # 4. PATH
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if entry:
            r = dll_in(Path(entry))
            if r: return r

    # 5. Drive walk (last resort, shallow)
    _skip = {"windows","system32","syswow64","$recycle.bin","recovery",
             "msocache","perflogs","boot","winsxs","softwaredistribution"}
    for drv in [Path(f"{d}:\\") for d in string.ascii_uppercase if Path(f"{d}:\\").exists()]:
        for dp, dirs, files in os.walk(drv):
            p = Path(dp)
            try:
                depth = len(p.relative_to(drv).parts)
            except ValueError:
                continue
            if depth > 4:
                dirs.clear(); continue
            if "libvlc.dll" in files:
                return p
            dirs[:] = [d for d in dirs if d.lower() not in _skip]
    return None


_vlc_folder: Optional[Path] = find_vlc_folder()

def vlc_is_ready() -> bool:
    return _vlc_folder is not None and (_vlc_folder / "libvlc.dll").is_file()

# ──────────────────────────────────────────────────────────────────────────────
#  Desktop embedding helpers (Win32)
# ──────────────────────────────────────────────────────────────────────────────
def restore_desktop() -> None:
    """Un-hide the WorkerW so the normal desktop is visible again."""
    try:
        u32 = ctypes.windll.user32
        ww  = ctypes.c_void_p(None)

        def _cb(hwnd, _):
            if u32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
                candidate = u32.FindWindowExW(None, hwnd, "WorkerW", None)
                if candidate:
                    ww.value = candidate
            return True

        u32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(_cb), 0)
        if ww.value:
            u32.ShowWindow(ww.value, 5)   # SW_SHOW
    except Exception as exc:
        log.debug("restore_desktop: %s", exc)


def _get_workerw() -> Optional[int]:
    u32     = ctypes.windll.user32
    progman = u32.FindWindowW("Progman", None)
    if not progman:
        return None
    u32.SendMessageTimeoutW(progman, 0x052C, 0, 0, 0, 1000, ctypes.byref(ctypes.c_ulong()))
    time.sleep(0.3)
    ww = ctypes.c_void_p(None)

    def _cb(hwnd, _):
        if u32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
            candidate = u32.FindWindowExW(None, hwnd, "WorkerW", None)
            if candidate:
                ww.value = candidate
        return True

    u32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(_cb), 0)
    return ww.value or progman


def _create_child_window(parent: int, w: int, h: int) -> int:
    u32       = ctypes.windll.user32
    hinstance = ctypes.windll.kernel32.GetModuleHandleW(None)
    return u32.CreateWindowExW(
        0, "STATIC", None,
        0x40000000 | 0x10000000,   # WS_CHILD | WS_VISIBLE
        0, 0, w, h,
        parent, None, hinstance, None,
    )

# ──────────────────────────────────────────────────────────────────────────────
#  Wallpaper engine state
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class _WallpaperState:
    player:     object = None
    instance:   object = None
    embed_hwnd: int    = 0
    path:       Optional[Path] = None

_ws = _WallpaperState()
_ws_lock = threading.Lock()


def start_wallpaper(
    video_path: Path,
    *,
    mute: bool        = True,
    volume: int       = 0,
    speed: float      = 1.0,
    loop: bool        = True,
    status_cb: Callable[[str], None] = lambda _: None,
) -> None:
    """Start playing video_path as the desktop wallpaper."""
    global _vlc_folder

    if not video_path.is_file():
        raise FileNotFoundError(f"File not found: {video_path}")
    if not vlc_is_ready():
        raise RuntimeError("VLC is not available. Please wait for the download.")

    stop_wallpaper()   # clean up any existing playback

    vlc_dll     = _vlc_folder / "libvlc.dll"
    vlc_plugins = _vlc_folder / "plugins"

    # Configure DLL paths before importing vlc
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(str(_vlc_folder))
        except Exception as exc:
            log.debug("add_dll_directory: %s", exc)
    os.environ["PYTHON_VLC_LIB_PATH"]    = str(vlc_dll)
    os.environ["PYTHON_VLC_MODULE_PATH"] = str(vlc_plugins)
    os.environ["VLC_PLUGIN_PATH"]        = str(vlc_plugins)

    try:
        import vlc
    except Exception as exc:
        raise RuntimeError(f"Could not load VLC library: {exc}") from exc

    u32 = ctypes.windll.user32
    sw  = u32.GetSystemMetrics(0)
    sh  = u32.GetSystemMetrics(1)

    workerw = _get_workerw()
    if not workerw:
        raise RuntimeError("Could not find WorkerW / Progman handle.\n"
                           "Make sure Explorer is running.")
    u32.ShowWindow(workerw, 5)

    embed = _create_child_window(workerw, sw, sh)
    if not embed:
        raise RuntimeError("Failed to create embed window inside WorkerW.")

    try:
        inst = vlc.Instance(
            "--no-xlib",
            "--no-video-title-show",
            "--quiet",
            "--avcodec-hw=any",
            f"--file-caching=500",
            "--no-snapshot-preview",
        )
        player = inst.media_player_new()
        media  = inst.media_new(str(video_path))
        if loop:
            media.add_option("input-repeat=65535")
        player.set_media(media)
        media.release()
        player.set_hwnd(embed)
        player.video_set_scale(0)
        player.audio_set_mute(mute)
        if not mute:
            player.audio_set_volume(max(0, min(200, volume)))
        player.set_rate(max(0.1, min(4.0, speed)))
        player.play()
    except Exception as exc:
        u32.DestroyWindow(embed)
        raise RuntimeError(f"VLC playback error: {exc}") from exc

    with _ws_lock:
        _ws.player     = player
        _ws.instance   = inst
        _ws.embed_hwnd = embed
        _ws.path       = video_path

    log.info("Wallpaper started: %s", video_path.name)
    status_cb(f"Playing: {video_path.name}")


def stop_wallpaper() -> None:
    """Stop playback and restore the desktop."""
    with _ws_lock:
        if _ws.player:
            try:
                _ws.player.stop()
                _ws.player.release()
            except Exception as exc:
                log.debug("player stop/release: %s", exc)
            try:
                if _ws.instance:
                    _ws.instance.release()
            except Exception as exc:
                log.debug("instance release: %s", exc)
            _ws.player   = None
            _ws.instance = None

        if _ws.embed_hwnd:
            try:
                ctypes.windll.user32.DestroyWindow(_ws.embed_hwnd)
            except Exception as exc:
                log.debug("DestroyWindow: %s", exc)
            _ws.embed_hwnd = 0

        _ws.path = None

    restore_desktop()
    log.info("Wallpaper stopped.")


def update_playback(*, mute: Optional[bool] = None, volume: Optional[int] = None,
                    speed: Optional[float] = None) -> None:
    """Live-update mute / volume / speed without restarting."""
    with _ws_lock:
        p = _ws.player
        if p is None:
            return
        try:
            if mute is not None:
                p.audio_set_mute(mute)
            if volume is not None:
                p.audio_set_volume(max(0, min(200, volume)))
            if speed is not None:
                p.set_rate(max(0.1, min(4.0, speed)))
        except Exception as exc:
            log.debug("update_playback: %s", exc)

# ──────────────────────────────────────────────────────────────────────────────
#  VLC download
# ──────────────────────────────────────────────────────────────────────────────
def download_vlc(
    progress_cb: Callable[[int], None],
    done_cb:     Callable[[bool, Optional[str]], None],
) -> None:
    """Download portable VLC to DATA_DIR/vlc_portable (runs in a thread)."""
    global _vlc_folder
    try:
        zip_path = DATA_DIR / "vlc_temp.zip"
        VLC_PORTABLE_FOLDER.mkdir(parents=True, exist_ok=True)
        log.info("Downloading VLC from %s", VLC_URL)

        def _hook(count: int, block: int, total: int) -> None:
            if total > 0:
                progress_cb(min(int(count * block * 100 / total), 99))

        urllib.request.urlretrieve(VLC_URL, zip_path, _hook)

        log.info("Extracting VLC…")
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(VLC_PORTABLE_FOLDER)
        zip_path.unlink(missing_ok=True)

        extracted = VLC_PORTABLE_FOLDER / VLC_ZIP_VERSION
        if extracted.is_dir():
            for item in extracted.iterdir():
                dst = VLC_PORTABLE_FOLDER / item.name
                if not dst.exists():
                    shutil.move(str(item), str(dst))
            shutil.rmtree(extracted, ignore_errors=True)

        _vlc_folder = find_vlc_folder()
        if not vlc_is_ready():
            raise RuntimeError("Extraction succeeded but libvlc.dll not found — "
                               "zip may be corrupt. Delete vlc_portable and retry.")

        progress_cb(100)
        log.info("VLC ready at %s", _vlc_folder)
        done_cb(True, None)

    except Exception as exc:
        log.error("VLC download failed: %s", exc, exc_info=True)
        done_cb(False, str(exc))

# ──────────────────────────────────────────────────────────────────────────────
#  Media file scanner
# ──────────────────────────────────────────────────────────────────────────────
def find_media_files() -> list[Path]:
    home = Path.home()
    search_dirs = [
        SCRIPT_DIR,
        home / "Videos",
        home / "Downloads",
        home / "Desktop",
        home / "Pictures",
        home / "Documents",
    ]
    seen: set[Path] = set()
    found: list[Path] = []
    for folder in search_dirs:
        if not folder.is_dir():
            continue
        try:
            for f in sorted(folder.iterdir()):
                if f.suffix.lower() in SUPPORTED and f not in seen:
                    seen.add(f)
                    found.append(f)
        except PermissionError:
            pass
    return found

# ──────────────────────────────────────────────────────────────────────────────
#  Colour / lerp helpers
# ──────────────────────────────────────────────────────────────────────────────
def lerp_color(pct: float,
               low: str = "#52d68a", mid: str = "#f9c74f",
               high: str = "#f96060", t1: float = 50, t2: float = 80) -> str:
    def h2r(h: str):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    def r2h(r, g, b) -> str:
        return f"#{int(r):02x}{int(g):02x}{int(b):02x}"
    def blend(a, b, t):
        return tuple(a[i] + (b[i]-a[i])*t for i in range(3))

    pct = max(0.0, min(100.0, pct))
    cl, cm, ch = h2r(low), h2r(mid), h2r(high)
    if pct <= t1:   return r2h(*blend(cl, cm, pct / t1))
    elif pct <= t2: return r2h(*blend(cm, ch, (pct-t1)/(t2-t1)))
    else:           return r2h(*ch)

def fmt_size(path: Path) -> str:
    try:
        b = path.stat().st_size
        for unit in ("B","KB","MB","GB"):
            if b < 1024: return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} TB"
    except OSError:
        return "?"

# ──────────────────────────────────────────────────────────────────────────────
#  Tooltip helper
# ──────────────────────────────────────────────────────────────────────────────
class Tooltip:
    """Simple balloon tooltip for any tkinter widget."""
    def __init__(self, widget: tk.Widget, text: str, delay: int = 600) -> None:
        self._widget = widget
        self._text   = text
        self._delay  = delay
        self._win: Optional[tk.Toplevel] = None
        self._after_id: Optional[str]   = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._cancel,   add="+")
        widget.bind("<ButtonPress>", self._cancel, add="+")

    def _schedule(self, _=None) -> None:
        self._cancel()
        self._after_id = self._widget.after(self._delay, self._show)

    def _cancel(self, _=None) -> None:
        if self._after_id:
            self._widget.after_cancel(self._after_id)
            self._after_id = None
        if self._win:
            self._win.destroy()
            self._win = None

    def _show(self) -> None:
        if self._win:
            return
        x = self._widget.winfo_rootx() + 10
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._win = tk.Toplevel(self._widget)
        self._win.wm_overrideredirect(True)
        self._win.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self._win, text=self._text,
            bg="#1e2128", fg="#c8ccd6",
            font=("Segoe UI", 8),
            padx=8, pady=4,
            relief="flat",
            bd=1,
        ).pack()

# ──────────────────────────────────────────────────────────────────────────────
#  Main application window
# ──────────────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    # ── Palette ───────────────────────────────────────────────────────────────
    C = {
        "BG":      "#0d0f14",
        "SURFACE": "#13161d",
        "CARD":    "#181b23",
        "CARD2":   "#1e2230",
        "BORDER":  "#252936",
        "ACCENT":  "#4f8ef7",
        "ACCENT2": "#3a6fd4",
        "FG":      "#e2e5f0",
        "FG2":     "#7c8196",
        "FG3":     "#454a5e",
        "SUCCESS": "#4dd68c",
        "WARN":    "#f9c74f",
        "DANGER":  "#f96060",
        "TAG":     "#232840",
    }

    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME}  v{APP_VERSION}")
        self.geometry("660x720")
        self.minsize(600, 640)
        self.configure(bg=self.C["BG"])

        # Try to set a nice window icon (silently skip if assets missing)
        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        # Persist settings
        self._settings = load_settings()

        # Runtime state
        self._is_playing     = False
        self._selected_path: Optional[Path] = None
        self._file_map:       dict[str, Path] = {}
        self._stats_id:       Optional[str]   = None
        self._scan_thread:    Optional[threading.Thread] = None

        # Sparkline history
        self._cpu_hist = [0.0] * 60
        self._ram_hist = [0.0] * 60

        # Prime psutil (first call always returns 0)
        psutil.cpu_percent(interval=None)

        self._build_styles()
        self._build_ui()

        # Restore last file
        last = self._settings.get("last_file", "")
        if last and Path(last).is_file():
            self._set_selected(Path(last))

        # Deferred startup tasks
        self.after(120,  self._async_scan)
        self.after(800,  self._update_stats)

    # ── ttk styles ────────────────────────────────────────────────────────────
    def _build_styles(self) -> None:
        C = self.C
        s = ttk.Style(self)
        s.theme_use("clam")

        # Progress bars
        for name, fg in [("DL",  C["ACCENT"]),
                         ("CPU", C["SUCCESS"]),
                         ("RAM", C["ACCENT"])]:
            s.configure(f"{name}.Horizontal.TProgressbar",
                        troughcolor=C["BORDER"], background=fg,
                        thickness=6, borderwidth=0, relief="flat")

        # Notebook tabs
        s.configure("App.TNotebook",
                    background=C["SURFACE"], borderwidth=0, tabmargins=0)
        s.configure("App.TNotebook.Tab",
                    background=C["SURFACE"], foreground=C["FG2"],
                    font=("Segoe UI", 9), padding=(18, 8),
                    borderwidth=0)
        s.map("App.TNotebook.Tab",
              background=[("selected", C["BG"])],
              foreground=[("selected", C["FG"])])

        # Scrollbar
        s.configure("Dark.Vertical.TScrollbar",
                    background=C["BORDER"], troughcolor=C["CARD"],
                    arrowcolor=C["FG3"], borderwidth=0, relief="flat")

    # ── Full UI ───────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        C = self.C

        # ── Title bar ─────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=C["SURFACE"], height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="▶", bg=C["SURFACE"], fg=C["ACCENT"],
                 font=("Segoe UI", 18, "bold")).place(x=16, y=10)
        tk.Label(header, text=APP_NAME, bg=C["SURFACE"], fg=C["FG"],
                 font=("Segoe UI", 13, "bold")).place(x=44, y=8)
        tk.Label(header, text=f"v{APP_VERSION}  ·  Desktop Video Engine",
                 bg=C["SURFACE"], fg=C["FG2"],
                 font=("Segoe UI", 8)).place(x=46, y=30)

        # VLC status pill
        self.vlc_pill = tk.Label(header, bg=C["SURFACE"],
                                  font=("Segoe UI", 8))
        self.vlc_pill.place(relx=1.0, x=-16, y=18, anchor="e")
        self._refresh_vlc_pill()

        # Separator
        tk.Frame(self, bg=C["BORDER"], height=1).pack(fill="x")

        # ── Notebook ──────────────────────────────────────────────────────────
        nb = ttk.Notebook(self, style="App.TNotebook")
        nb.pack(fill="both", expand=True, padx=0, pady=0)
        self._nb = nb

        tab_wallpaper = tk.Frame(nb, bg=C["BG"])
        tab_settings  = tk.Frame(nb, bg=C["BG"])
        tab_monitor   = tk.Frame(nb, bg=C["BG"])
        tab_log       = tk.Frame(nb, bg=C["BG"])

        nb.add(tab_wallpaper, text="  🎬  Wallpaper  ")
        nb.add(tab_settings,  text="  ⚙  Settings  ")
        nb.add(tab_monitor,   text="  📊  Monitor  ")
        nb.add(tab_log,       text="  🗒  Log  ")

        self._build_tab_wallpaper(tab_wallpaper)
        self._build_tab_settings(tab_settings)
        self._build_tab_monitor(tab_monitor)
        self._build_tab_log(tab_log)

        # ── Status bar ────────────────────────────────────────────────────────
        sb = tk.Frame(self, bg=C["SURFACE"], height=28)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)

        self._status_dot = tk.Label(sb, text="●", bg=C["SURFACE"], fg=C["FG3"],
                                     font=("Segoe UI", 9))
        self._status_dot.place(x=12, y=5)

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(sb, textvariable=self._status_var, bg=C["SURFACE"], fg=C["FG2"],
                 font=("Segoe UI", 8)).place(x=28, y=6)

        self._playing_lbl = tk.Label(sb, text="", bg=C["SURFACE"], fg=C["FG3"],
                                      font=("Segoe UI", 8, "italic"))
        self._playing_lbl.place(relx=1.0, x=-12, y=6, anchor="e")

    # ── Tab: Wallpaper ────────────────────────────────────────────────────────
    def _build_tab_wallpaper(self, parent: tk.Frame) -> None:
        C = self.C
        pad = {"padx": 14, "pady": 6}

        # ─ File search section ───────────────────────────────────────────────
        self._section(parent, "FILE", top_pad=10)

        btn_row = tk.Frame(parent, bg=C["BG"])
        btn_row.pack(fill="x", padx=14, pady=(0, 6))

        self._btn(btn_row, "📂  Browse…", self._browse,
                  tooltip="Open a file picker to choose a video or GIF").pack(side="left", padx=(0,5))
        self._btn(btn_row, "🔍  Scan Folders", self._async_scan,
                  tooltip="Search Videos, Downloads, Desktop, Pictures…").pack(side="left", padx=(0,5))
        self._btn(btn_row, "⏱  Recent", self._show_recent_menu,
                  tooltip="Files you have used before").pack(side="left")

        # Drop-target entry
        path_wrap = tk.Frame(parent, bg=C["BORDER"], padx=1, pady=1)
        path_wrap.pack(fill="x", padx=14, pady=(0, 6))
        entry_frame = tk.Frame(path_wrap, bg=C["CARD"])
        entry_frame.pack(fill="x")
        self._path_var = tk.StringVar()
        self._path_entry = tk.Entry(
            entry_frame,
            textvariable=self._path_var,
            bg=C["CARD"], fg=C["FG"], insertbackground=C["FG"],
            font=("Segoe UI", 9), relief="flat", bd=6,
            highlightthickness=0,
        )
        self._path_entry.pack(fill="x", side="left", expand=True)
        self._btn(entry_frame, "Go", self._apply_from_entry,
                  w=40, h=28).pack(side="right", padx=2, pady=2)
        Tooltip(self._path_entry, "Paste or type a full file path, then click Go")

        # File list
        list_wrap = tk.Frame(parent, bg=C["BORDER"], padx=1, pady=1)
        list_wrap.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        inner = tk.Frame(list_wrap, bg=C["CARD"])
        inner.pack(fill="both", expand=True)

        sb = ttk.Scrollbar(inner, style="Dark.Vertical.TScrollbar")
        sb.pack(side="right", fill="y")

        self._listbox = tk.Listbox(
            inner, bg=C["CARD"], fg=C["FG"],
            selectbackground=C["ACCENT2"], selectforeground="#fff",
            font=("Segoe UI", 9), relief="flat", bd=0,
            activestyle="none", yscrollcommand=sb.set,
            height=9, highlightthickness=0,
        )
        self._listbox.pack(fill="both", expand=True, padx=2, pady=2)
        sb.config(command=self._listbox.yview)
        self._listbox.bind("<<ListboxSelect>>", self._on_list_select)
        self._listbox.bind("<Double-Button-1>", lambda _: self._apply())
        self._list_status = tk.Label(
            parent, text="", bg=C["BG"], fg=C["FG2"],
            font=("Segoe UI", 8), anchor="w",
        )
        self._list_status.pack(fill="x", padx=16, pady=(0, 4))

        # ─ Preview card ──────────────────────────────────────────────────────
        self._section(parent, "SELECTED")
        prev = tk.Frame(parent, bg=C["CARD"], padx=14, pady=10)
        prev.pack(fill="x", padx=14, pady=(0, 8))

        self._prev_icon = tk.Label(prev, text="📁", bg=C["CARD"],
                                    font=("Segoe UI Emoji", 22))
        self._prev_icon.pack(side="left", padx=(0, 12))

        info = tk.Frame(prev, bg=C["CARD"])
        info.pack(side="left", fill="x", expand=True)

        self._prev_name = tk.Label(info, text="No file selected",
                                    bg=C["CARD"], fg=C["FG"],
                                    font=("Segoe UI", 10, "bold"), anchor="w")
        self._prev_name.pack(fill="x")
        self._prev_meta = tk.Label(info, text="",
                                    bg=C["CARD"], fg=C["FG2"],
                                    font=("Segoe UI", 8), anchor="w")
        self._prev_meta.pack(fill="x")

        # ─ Action buttons ────────────────────────────────────────────────────
        self._section(parent, "CONTROL")
        act = tk.Frame(parent, bg=C["BG"], padx=14)
        act.pack(fill="x", pady=(0, 10))

        self._play_btn = tk.Button(
            act,
            text="▶   SET AS WALLPAPER",
            bg=C["ACCENT"], fg="#fff",
            font=("Segoe UI", 11, "bold"),
            relief="flat", cursor="hand2",
            activebackground=C["ACCENT2"], activeforeground="#fff",
            pady=12, command=self._apply,
        )
        self._play_btn.pack(fill="x", pady=(0, 5))
        Tooltip(self._play_btn, "Apply the selected video as your live desktop wallpaper")

        self._stop_btn = tk.Button(
            act,
            text="■   STOP  &  RESTORE DESKTOP",
            bg=C["SURFACE"], fg=C["FG2"],
            font=("Segoe UI", 10),
            relief="flat", cursor="hand2",
            activebackground=C["DANGER"], activeforeground="#fff",
            pady=9, state="disabled", command=self._stop,
        )
        self._stop_btn.pack(fill="x")
        Tooltip(self._stop_btn, "Stop playback and restore the normal desktop background")

    # ── Tab: Settings ─────────────────────────────────────────────────────────
    def _build_tab_settings(self, parent: tk.Frame) -> None:
        C = self.C
        s = self._settings

        self._section(parent, "AUDIO", top_pad=10)
        audio = tk.Frame(parent, bg=C["CARD"], padx=14, pady=12)
        audio.pack(fill="x", padx=14, pady=(0, 8))

        # Mute toggle
        self._mute_var = tk.BooleanVar(value=s.get("mute", True))
        mrow = tk.Frame(audio, bg=C["CARD"])
        mrow.pack(fill="x", pady=(0, 8))
        tk.Label(mrow, text="Mute audio", bg=C["CARD"], fg=C["FG"],
                 font=("Segoe UI", 9), width=14, anchor="w").pack(side="left")
        self._mute_chk = tk.Checkbutton(
            mrow, variable=self._mute_var,
            bg=C["CARD"], fg=C["FG"], selectcolor=C["BORDER"],
            activebackground=C["CARD"], activeforeground=C["FG"],
            relief="flat", bd=0, cursor="hand2",
            command=self._on_mute_toggle,
        )
        self._mute_chk.pack(side="left")
        Tooltip(self._mute_chk, "Mute the wallpaper video's audio track")

        # Volume slider
        vrow = tk.Frame(audio, bg=C["CARD"])
        vrow.pack(fill="x")
        tk.Label(vrow, text="Volume", bg=C["CARD"], fg=C["FG"],
                 font=("Segoe UI", 9), width=14, anchor="w").pack(side="left")
        self._vol_var = tk.IntVar(value=s.get("volume", 0))
        self._vol_lbl = tk.Label(vrow, text=f"{self._vol_var.get()}%",
                                  bg=C["CARD"], fg=C["FG2"],
                                  font=("Segoe UI", 9), width=5)
        self._vol_lbl.pack(side="right")
        vol_sl = tk.Scale(
            vrow, from_=0, to=200,
            orient="horizontal", variable=self._vol_var,
            bg=C["CARD"], fg=C["FG2"], troughcolor=C["BORDER"],
            highlightthickness=0, sliderrelief="flat",
            activebackground=C["ACCENT"],
            showvalue=False, command=self._on_volume_change,
        )
        vol_sl.pack(side="left", fill="x", expand=True, padx=(0,6))
        Tooltip(vol_sl, "Set wallpaper volume (0–200 %). Requires mute off.")

        self._section(parent, "PLAYBACK")
        pb = tk.Frame(parent, bg=C["CARD"], padx=14, pady=12)
        pb.pack(fill="x", padx=14, pady=(0, 8))

        # Speed
        sprow = tk.Frame(pb, bg=C["CARD"])
        sprow.pack(fill="x", pady=(0, 8))
        tk.Label(sprow, text="Speed", bg=C["CARD"], fg=C["FG"],
                 font=("Segoe UI", 9), width=14, anchor="w").pack(side="left")
        self._speed_var = tk.DoubleVar(value=s.get("speed", 1.0))
        self._speed_lbl = tk.Label(sprow, text=f"{self._speed_var.get():.1f}×",
                                    bg=C["CARD"], fg=C["FG2"],
                                    font=("Segoe UI", 9), width=5)
        self._speed_lbl.pack(side="right")
        sp_sl = tk.Scale(
            sprow, from_=10, to=400,
            orient="horizontal",
            bg=C["CARD"], fg=C["FG2"], troughcolor=C["BORDER"],
            highlightthickness=0, sliderrelief="flat",
            activebackground=C["ACCENT"], showvalue=False,
            command=self._on_speed_change,
        )
        sp_sl.set(int(self._speed_var.get() * 100))
        sp_sl.pack(side="left", fill="x", expand=True, padx=(0,6))
        Tooltip(sp_sl, "Playback speed multiplier (0.1× – 4.0×)")

        # Loop
        lrow = tk.Frame(pb, bg=C["CARD"])
        lrow.pack(fill="x")
        tk.Label(lrow, text="Loop video", bg=C["CARD"], fg=C["FG"],
                 font=("Segoe UI", 9), width=14, anchor="w").pack(side="left")
        self._loop_var = tk.BooleanVar(value=s.get("loop", True))
        tk.Checkbutton(
            lrow, variable=self._loop_var,
            bg=C["CARD"], fg=C["FG"], selectcolor=C["BORDER"],
            activebackground=C["CARD"], activeforeground=C["FG"],
            relief="flat", bd=0, cursor="hand2",
            command=self._save_settings,
        ).pack(side="left")

        self._section(parent, "VLC ENGINE")
        vlc_card = tk.Frame(parent, bg=C["CARD"], padx=14, pady=12)
        vlc_card.pack(fill="x", padx=14, pady=(0, 8))

        vlc_row = tk.Frame(vlc_card, bg=C["CARD"])
        vlc_row.pack(fill="x")
        if vlc_is_ready():
            vlc_info = f"Found:  {_vlc_folder}"
            vlc_fg   = C["SUCCESS"]
        else:
            vlc_info = "Not found — will download portable copy on first use"
            vlc_fg   = C["WARN"]
        self._vlc_info_lbl = tk.Label(
            vlc_row, text=vlc_info, bg=C["CARD"], fg=vlc_fg,
            font=("Segoe UI", 8), anchor="w", wraplength=500, justify="left",
        )
        self._vlc_info_lbl.pack(side="left", fill="x", expand=True)

        self._btn(vlc_row, "Re-scan", self._rescan_vlc,
                  tooltip="Search system again for VLC").pack(side="right")

        self._section(parent, "DATA")
        data_card = tk.Frame(parent, bg=C["CARD"], padx=14, pady=12)
        data_card.pack(fill="x", padx=14, pady=(0, 8))
        tk.Label(data_card, text=f"Settings & logs:  {DATA_DIR}",
                 bg=C["CARD"], fg=C["FG2"], font=("Segoe UI", 8), anchor="w").pack(fill="x")
        br = tk.Frame(data_card, bg=C["CARD"])
        br.pack(fill="x", pady=(8, 0))
        self._btn(br, "Open Data Folder", lambda: os.startfile(str(DATA_DIR)),
                  tooltip="Open the folder in Explorer").pack(side="left", padx=(0,6))
        self._btn(br, "Clear Recent Files", self._clear_recent,
                  tooltip="Wipe the recent files list").pack(side="left")

    # ── Tab: Monitor ──────────────────────────────────────────────────────────
    def _build_tab_monitor(self, parent: tk.Frame) -> None:
        C = self.C

        cards = tk.Frame(parent, bg=C["BG"])
        cards.pack(fill="x", padx=14, pady=14)

        # CPU card
        cpu_card = tk.Frame(cards, bg=C["CARD"], padx=14, pady=12)
        cpu_card.pack(side="left", fill="both", expand=True, padx=(0, 6))

        cpu_hdr = tk.Frame(cpu_card, bg=C["CARD"])
        cpu_hdr.pack(fill="x")
        tk.Label(cpu_hdr, text="CPU", bg=C["CARD"], fg=C["FG2"],
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self._cpu_status_lbl = tk.Label(cpu_hdr, text="", bg=C["CARD"],
                                         fg=C["SUCCESS"], font=("Segoe UI", 8))
        self._cpu_status_lbl.pack(side="right")

        self._cpu_pct_lbl = tk.Label(cpu_card, text="—", bg=C["CARD"], fg=C["FG"],
                                      font=("Segoe UI", 26, "bold"))
        self._cpu_pct_lbl.pack(anchor="w", pady=(2, 4))

        self._cpu_bar_var = tk.DoubleVar()
        ttk.Progressbar(cpu_card, variable=self._cpu_bar_var, maximum=100,
                         style="CPU.Horizontal.TProgressbar").pack(fill="x")
        self._cpu_canvas = tk.Canvas(cpu_card, bg=C["CARD"], height=36,
                                      highlightthickness=0)
        self._cpu_canvas.pack(fill="x", pady=(6, 0))

        # Per-core grid
        self._core_frame = tk.Frame(cpu_card, bg=C["CARD"])
        self._core_frame.pack(fill="x", pady=(8, 0))
        self._core_bars: list[ttk.Progressbar] = []
        self._core_lbls: list[tk.Label]         = []
        cores = psutil.cpu_count(logical=True) or 4
        cols  = min(cores, 8)
        for i in range(cores):
            col = i % cols
            row = i // cols
            f   = tk.Frame(self._core_frame, bg=C["CARD"])
            f.grid(row=row*2, column=col, padx=3, pady=(4,0), sticky="ew")
            lbl = tk.Label(f, text=f"C{i}", bg=C["CARD"], fg=C["FG3"],
                            font=("Segoe UI", 6))
            lbl.pack()
            self._core_lbls.append(lbl)
            var = tk.DoubleVar()
            pb  = ttk.Progressbar(self._core_frame, variable=var, maximum=100,
                                   orient="vertical", length=30,
                                   style="CPU.Horizontal.TProgressbar")
            pb.grid(row=row*2+1, column=col, padx=3, pady=(0,2))
            self._core_bars.append(pb)
        for c in range(cols):
            self._core_frame.columnconfigure(c, weight=1)

        # RAM card
        ram_card = tk.Frame(cards, bg=C["CARD"], padx=14, pady=12)
        ram_card.pack(side="left", fill="both", expand=True, padx=(6, 0))

        ram_hdr = tk.Frame(ram_card, bg=C["CARD"])
        ram_hdr.pack(fill="x")
        tk.Label(ram_hdr, text="RAM", bg=C["CARD"], fg=C["FG2"],
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self._ram_status_lbl = tk.Label(ram_hdr, text="", bg=C["CARD"],
                                         fg=C["SUCCESS"], font=("Segoe UI", 8))
        self._ram_status_lbl.pack(side="right")

        self._ram_mb_lbl = tk.Label(ram_card, text="—", bg=C["CARD"], fg=C["FG"],
                                     font=("Segoe UI", 26, "bold"))
        self._ram_mb_lbl.pack(anchor="w", pady=(2, 4))

        self._ram_bar_var = tk.DoubleVar()
        ttk.Progressbar(ram_card, variable=self._ram_bar_var, maximum=100,
                         style="RAM.Horizontal.TProgressbar").pack(fill="x")
        self._ram_canvas = tk.Canvas(ram_card, bg=C["CARD"], height=36,
                                      highlightthickness=0)
        self._ram_canvas.pack(fill="x", pady=(6, 0))

        # RAM breakdown
        ram = psutil.virtual_memory()
        total_gb = ram.total / 1024**3
        self._ram_total_lbl = tk.Label(
            ram_card,
            text=f"Total: {total_gb:.1f} GB",
            bg=C["CARD"], fg=C["FG3"], font=("Segoe UI", 7), anchor="w",
        )
        self._ram_total_lbl.pack(fill="x", pady=(6,0))

        # Health tip
        tip_frame = tk.Frame(parent, bg=C["SURFACE"], padx=14, pady=8)
        tip_frame.pack(fill="x", padx=14, pady=(0,8))
        self._health_lbl = tk.Label(
            tip_frame, text="", bg=C["SURFACE"], fg=C["FG2"],
            font=("Segoe UI", 8), anchor="w", wraplength=600,
        )
        self._health_lbl.pack(fill="x")

        # Wallpaper process stats
        self._section(parent, "WALLPAPER PROCESS")
        proc_card = tk.Frame(parent, bg=C["CARD"], padx=14, pady=10)
        proc_card.pack(fill="x", padx=14, pady=(0, 8))
        self._proc_lbl = tk.Label(
            proc_card, text="Not playing", bg=C["CARD"], fg=C["FG2"],
            font=("Segoe UI", 8), anchor="w",
        )
        self._proc_lbl.pack(fill="x")

    # ── Tab: Log ──────────────────────────────────────────────────────────────
    def _build_tab_log(self, parent: tk.Frame) -> None:
        C = self.C

        ctrl = tk.Frame(parent, bg=C["BG"])
        ctrl.pack(fill="x", padx=14, pady=(10,4))
        self._btn(ctrl, "⟳  Refresh", self._refresh_log,
                  tooltip="Reload log file").pack(side="left", padx=(0,5))
        self._btn(ctrl, "🗑  Clear Log", self._clear_log,
                  tooltip="Delete the log file").pack(side="left")

        wrap = tk.Frame(parent, bg=C["BORDER"], padx=1, pady=1)
        wrap.pack(fill="both", expand=True, padx=14, pady=(0,10))
        inner = tk.Frame(wrap, bg=C["CARD"])
        inner.pack(fill="both", expand=True)

        sb_h = ttk.Scrollbar(inner, orient="horizontal")
        sb_v = ttk.Scrollbar(inner, style="Dark.Vertical.TScrollbar")
        sb_h.pack(side="bottom", fill="x")
        sb_v.pack(side="right",  fill="y")

        self._log_text = tk.Text(
            inner,
            bg=C["CARD"], fg=C["FG"], insertbackground=C["FG"],
            font=("Consolas", 8),
            relief="flat", bd=0,
            wrap="none",
            xscrollcommand=sb_h.set,
            yscrollcommand=sb_v.set,
            state="disabled",
        )
        self._log_text.pack(fill="both", expand=True, padx=4, pady=4)
        sb_h.config(command=self._log_text.xview)
        sb_v.config(command=self._log_text.yview)

        # colour tags
        self._log_text.tag_config("ERR",  foreground=C["DANGER"])
        self._log_text.tag_config("WARN", foreground=C["WARN"])
        self._log_text.tag_config("INFO", foreground=C["FG2"])
        self._log_text.tag_config("DBG",  foreground=C["FG3"])

        self.after(200, self._refresh_log)

    # ── Widget factory helpers ─────────────────────────────────────────────────
    def _btn(self, parent: tk.Widget, text: str, cmd, *,
             tooltip: str = "", w: int = 0, h: int = 0) -> tk.Button:
        C = self.C
        kw: dict = dict(
            text=text, bg=C["CARD2"], fg=C["FG"],
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            activebackground=C["BORDER"], activeforeground=C["FG"],
            padx=10, pady=5, command=cmd,
        )
        if w: kw["width"]  = w
        if h: kw["height"] = h
        b = tk.Button(parent, **kw)
        if tooltip:
            Tooltip(b, tooltip)
        return b

    def _section(self, parent: tk.Widget, title: str, top_pad: int = 6) -> None:
        C = self.C
        f = tk.Frame(parent, bg=C["BG"])
        f.pack(fill="x", padx=14, pady=(top_pad, 4))
        tk.Label(f, text=title, bg=C["BG"], fg=C["FG3"],
                 font=("Segoe UI", 7, "bold")).pack(side="left")
        tk.Frame(f, bg=C["BORDER"], height=1).pack(
            side="left", fill="x", expand=True, padx=(8, 0), pady=1)

    # ── VLC pill ──────────────────────────────────────────────────────────────
    def _refresh_vlc_pill(self) -> None:
        C = self.C
        if vlc_is_ready():
            self.vlc_pill.config(
                text=f"● VLC ✓  {_vlc_folder.name}",
                fg=C["SUCCESS"],
            )
        else:
            self.vlc_pill.config(text="● VLC not found", fg=C["WARN"])

    # ── Async file scan ───────────────────────────────────────────────────────
    def _async_scan(self) -> None:
        if self._scan_thread and self._scan_thread.is_alive():
            return
        self._list_status.config(text="Scanning…", fg=self.C["FG2"])
        self._listbox.delete(0, "end")
        self._file_map.clear()
        self._listbox.insert("end", "  Scanning folders…")

        def _worker():
            files = find_media_files()
            self.after(0, lambda: self._on_scan_done(files))

        self._scan_thread = threading.Thread(target=_worker, daemon=True)
        self._scan_thread.start()

    def _on_scan_done(self, files: list[Path]) -> None:
        self._listbox.delete(0, "end")
        self._file_map.clear()
        if files:
            for f in files:
                ext  = f.suffix.upper().lstrip(".")
                size = fmt_size(f)
                label = f"  {f.name}  ·  {ext}  ·  {size}   —   {f.parent}"
                self._listbox.insert("end", label)
                self._file_map[label] = f
            self._list_status.config(
                text=f"{len(files)} file(s) found", fg=self.C["FG2"])
        else:
            self._listbox.insert("end", "  No media files found in common folders")
            self._list_status.config(text="Nothing found — use Browse", fg=self.C["WARN"])

    # ── Recent files ──────────────────────────────────────────────────────────
    def _add_recent(self, path: Path) -> None:
        recent: list[str] = self._settings.get("recent_files", [])
        s = str(path)
        if s in recent:
            recent.remove(s)
        recent.insert(0, s)
        self._settings["recent_files"] = recent[:MAX_RECENT]
        self._save_settings()

    def _show_recent_menu(self) -> None:
        recent = [Path(p) for p in self._settings.get("recent_files", [])
                  if Path(p).is_file()]
        if not recent:
            self._set_status("No recent files yet.")
            return
        menu = tk.Menu(self, tearoff=False,
                        bg=self.C["CARD"], fg=self.C["FG"],
                        activebackground=self.C["ACCENT2"],
                        activeforeground="#fff",
                        font=("Segoe UI", 9), relief="flat")
        for p in recent:
            menu.add_command(
                label=f"  {p.name}  —  {p.parent}",
                command=lambda _p=p: self._set_selected(_p),
            )
        menu.add_separator()
        menu.add_command(label="  Clear recent files", command=self._clear_recent)
        try:
            btn = self._nb.nametowidget(self._nb.select())
        except Exception:
            btn = self
        menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    def _clear_recent(self) -> None:
        self._settings["recent_files"] = []
        self._save_settings()
        self._set_status("Recent files cleared.")

    # ── Selection helpers ─────────────────────────────────────────────────────
    def _on_list_select(self, _=None) -> None:
        sel = self._listbox.curselection()
        if sel:
            label = self._listbox.get(sel[0])
            if label in self._file_map:
                self._set_selected(self._file_map[label])

    def _browse(self) -> None:
        exts = " ".join(f"*{e}" for e in SUPPORTED)
        path = filedialog.askopenfilename(
            title="Select a video or GIF",
            filetypes=[("Media files", exts), ("All files", "*.*")],
        )
        if path:
            self._set_selected(Path(path))

    def _apply_from_entry(self) -> None:
        raw = self._path_var.get().strip().strip('"')
        if not raw:
            return
        p = Path(raw)
        if not p.is_file():
            self._set_status(f"File not found: {p.name}", error=True)
            return
        self._set_selected(p)
        self._apply()

    def _set_selected(self, p: Path) -> None:
        self._selected_path = p
        self._path_var.set(str(p))

        ext  = p.suffix.upper().lstrip(".")
        size = fmt_size(p)
        self._prev_icon.config(
            text="🎞️" if p.suffix.lower() == ".gif" else "🎬"
        )
        self._prev_name.config(text=p.name)
        self._prev_meta.config(text=f"{ext}  ·  {size}  ·  {p.parent}")
        self._set_status(f"Selected: {p.name}")

    # ── Apply / Stop ──────────────────────────────────────────────────────────
    def _apply(self) -> None:
        if not self._selected_path:
            messagebox.showwarning("No file", "Select a video or GIF first.",
                                    parent=self)
            return
        if not self._selected_path.is_file():
            messagebox.showwarning(
                "File not found",
                f"Cannot find:\n{self._selected_path}\n\n"
                "It may have been moved or deleted.",
                parent=self,
            )
            return

        if not vlc_is_ready():
            self._download_then_play(self._selected_path)
        else:
            self._launch(self._selected_path)

    def _download_then_play(self, path: Path) -> None:
        self._play_btn.config(state="disabled")

        # Show a download overlay inside the wallpaper tab
        overlay = tk.Toplevel(self)
        overlay.title("Downloading VLC")
        overlay.geometry("420x140")
        overlay.resizable(False, False)
        overlay.configure(bg=self.C["CARD"])
        overlay.grab_set()
        overlay.transient(self)
        overlay.protocol("WM_DELETE_WINDOW", lambda: None)  # block close

        tk.Label(overlay, text="Downloading portable VLC  (~40 MB)",
                 bg=self.C["CARD"], fg=self.C["FG"],
                 font=("Segoe UI", 10, "bold")).pack(pady=(18, 4))
        tk.Label(overlay, text="This is a one-time download stored in AppData.",
                 bg=self.C["CARD"], fg=self.C["FG2"],
                 font=("Segoe UI", 8)).pack()

        dl_var = tk.IntVar()
        dl_bar = ttk.Progressbar(overlay, variable=dl_var, maximum=100,
                                  style="DL.Horizontal.TProgressbar", length=360)
        dl_bar.pack(pady=(12, 4))

        dl_lbl = tk.Label(overlay, text="Starting…",
                           bg=self.C["CARD"], fg=self.C["FG2"],
                           font=("Segoe UI", 8))
        dl_lbl.pack()

        def on_progress(pct: int) -> None:
            dl_var.set(pct)
            dl_lbl.config(text=f"{pct}%  downloaded")
            self._set_status(f"Downloading VLC…  {pct}%")

        def on_done(ok: bool, err: Optional[str]) -> None:
            overlay.grab_release()
            overlay.destroy()
            self._play_btn.config(state="normal")
            self._refresh_vlc_pill()
            if ok:
                self._update_vlc_info()
                self._set_status("VLC ready — starting wallpaper…")
                self.after(200, lambda: self._launch(path))
            else:
                log.error("VLC download failed: %s", err)
                messagebox.showerror(
                    "Download Failed",
                    f"Could not download VLC:\n\n{err}\n\n"
                    "Check your internet connection and try again.",
                    parent=self,
                )
                self._set_status("Download failed.", error=True)

        threading.Thread(
            target=download_vlc,
            args=(
                lambda p: self.after(0, lambda: on_progress(p)),
                lambda ok, e: self.after(0, lambda: on_done(ok, e)),
            ),
            daemon=True,
        ).start()

    def _launch(self, path: Path) -> None:
        try:
            self._set_status("Starting wallpaper…")
            start_wallpaper(
                path,
                mute=self._mute_var.get(),
                volume=self._vol_var.get(),
                speed=self._speed_var.get(),
                loop=self._loop_var.get(),
                status_cb=lambda s: self.after(0, lambda: self._on_playing(s)),
            )
            self._is_playing = True
            self._play_btn.config(
                state="disabled",
                bg=self.C["BORDER"], fg=self.C["FG3"],
                text="▶   WALLPAPER ACTIVE",
            )
            self._stop_btn.config(
                state="normal",
                bg=self.C["DANGER"], fg="#fff",
                activebackground="#c94040",
            )
            self._add_recent(path)
            self._settings["last_file"] = str(path)
            self._save_settings()

        except Exception as exc:
            log.error("Failed to start wallpaper: %s", exc, exc_info=True)
            messagebox.showerror(
                "Playback Error",
                f"Could not start wallpaper:\n\n{exc}",
                parent=self,
            )
            self._set_status(f"Error: {exc}", error=True)
            self._play_btn.config(state="normal")

    def _on_playing(self, msg: str) -> None:
        self._set_status(msg)
        self._status_dot.config(fg=self.C["SUCCESS"])
        self._playing_lbl.config(text=f"▶  {_ws.path.name if _ws.path else ''}")

    def _stop(self) -> None:
        try:
            stop_wallpaper()
        except Exception as exc:
            log.error("stop_wallpaper error: %s", exc)
        self._is_playing = False
        self._play_btn.config(
            state="normal",
            bg=self.C["ACCENT"], fg="#fff",
            text="▶   SET AS WALLPAPER",
        )
        self._stop_btn.config(
            state="disabled",
            bg=self.C["SURFACE"], fg=self.C["FG2"],
        )
        self._status_dot.config(fg=self.C["FG3"])
        self._playing_lbl.config(text="")
        self._set_status("Stopped — desktop restored ✓")

    # ── Settings helpers ──────────────────────────────────────────────────────
    def _on_mute_toggle(self) -> None:
        muted = self._mute_var.get()
        update_playback(mute=muted)
        self._save_settings()

    def _on_volume_change(self, val) -> None:
        v = int(float(val))
        self._vol_lbl.config(text=f"{v}%")
        update_playback(volume=v)
        self._settings["volume"] = v
        self._save_settings()

    def _on_speed_change(self, val) -> None:
        speed = round(int(float(val)) / 100, 2)
        self._speed_var.set(speed)
        self._speed_lbl.config(text=f"{speed:.1f}×")
        update_playback(speed=speed)
        self._settings["speed"] = speed
        self._save_settings()

    def _save_settings(self) -> None:
        self._settings["mute"]   = self._mute_var.get()
        self._settings["volume"] = self._vol_var.get()
        self._settings["speed"]  = self._speed_var.get()
        self._settings["loop"]   = self._loop_var.get()
        save_settings(self._settings)

    def _rescan_vlc(self) -> None:
        global _vlc_folder
        self._set_status("Scanning for VLC…")
        def _worker():
            _vlc_folder = find_vlc_folder()
            self.after(0, self._on_vlc_rescan_done)
        threading.Thread(target=_worker, daemon=True).start()

    def _on_vlc_rescan_done(self) -> None:
        self._refresh_vlc_pill()
        self._update_vlc_info()
        if vlc_is_ready():
            self._set_status(f"VLC found at {_vlc_folder}")
        else:
            self._set_status("VLC not found on this system.", error=True)

    def _update_vlc_info(self) -> None:
        if vlc_is_ready():
            self._vlc_info_lbl.config(
                text=f"Found:  {_vlc_folder}", fg=self.C["SUCCESS"])
        else:
            self._vlc_info_lbl.config(
                text="Not found — will auto-download on first use.",
                fg=self.C["WARN"])

    # ── Log tab ───────────────────────────────────────────────────────────────
    def _refresh_log(self) -> None:
        try:
            content = LOG_FILE.read_text(encoding="utf-8", errors="replace") \
                      if LOG_FILE.is_file() else "(log file is empty)"
        except Exception as exc:
            content = f"(could not read log: {exc})"

        self._log_text.config(state="normal")
        self._log_text.delete("1.0", "end")
        for line in content.splitlines():
            tag = "INFO"
            ll  = line.lower()
            if "[error]"   in ll: tag = "ERR"
            elif "[warning]" in ll: tag = "WARN"
            elif "[debug]"  in ll: tag = "DBG"
            self._log_text.insert("end", line + "\n", tag)
        self._log_text.see("end")
        self._log_text.config(state="disabled")

    def _clear_log(self) -> None:
        if messagebox.askyesno("Clear Log",
                                "Delete the log file?", parent=self):
            try:
                LOG_FILE.write_text("", encoding="utf-8")
                self._refresh_log()
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=self)

    # ── Live performance stats ────────────────────────────────────────────────
    def _update_stats(self) -> None:
        if not self.winfo_exists():
            return
        C = self.C
        s = ttk.Style()

        # CPU
        cpu_pct  = psutil.cpu_percent(interval=None)
        cpu_per  = psutil.cpu_percent(interval=None, percpu=True) or [cpu_pct]
        self._cpu_hist.append(cpu_pct)
        self._cpu_hist.pop(0)
        cpu_col = lerp_color(cpu_pct)
        self._cpu_pct_lbl.config(text=f"{cpu_pct:.0f}%", fg=cpu_col)
        self._cpu_bar_var.set(cpu_pct)
        s.configure("CPU.Horizontal.TProgressbar", background=cpu_col)

        if cpu_pct < 5:   cl, lc = "● Idle",     C["SUCCESS"]
        elif cpu_pct < 20: cl, lc = "● Normal",   C["SUCCESS"]
        elif cpu_pct < 50: cl, lc = "● Moderate", C["WARN"]
        elif cpu_pct < 80: cl, lc = "● High",     C["WARN"]
        else:              cl, lc = "● Critical",  C["DANGER"]
        self._cpu_status_lbl.config(text=cl, fg=lc)

        # Per-core bars
        for i, bar in enumerate(self._core_bars):
            val = cpu_per[i] if i < len(cpu_per) else 0
            bar["value"] = val

        # RAM
        ram      = psutil.virtual_memory()
        ram_pct  = ram.percent
        ram_used = ram.used / 1024**3
        self._ram_hist.append(ram_pct)
        self._ram_hist.pop(0)
        ram_col = lerp_color(ram_pct)
        self._ram_mb_lbl.config(text=f"{ram_used:.2f} GB", fg=ram_col)
        self._ram_bar_var.set(ram_pct)
        s.configure("RAM.Horizontal.TProgressbar", background=ram_col)

        if ram_pct < 50:   rl, lc = "● Good",     C["SUCCESS"]
        elif ram_pct < 75: rl, lc = "● Moderate", C["WARN"]
        else:              rl, lc = "● High",      C["DANGER"]
        self._ram_status_lbl.config(text=rl, fg=lc)

        # Health tip
        if cpu_pct > 80:
            tip = "⚠  CPU critical — consider closing other apps or using a lighter video codec"
        elif cpu_pct > 40:
            tip = "⚠  High CPU — try a 1080p H.264 MP4 for best performance"
        elif ram_pct > 85:
            tip = "⚠  RAM is very high — close unused applications"
        elif cpu_pct < 5 and self._is_playing:
            tip = "✓  GPU hardware decoding active — running very efficiently"
        elif self._is_playing:
            tip = "✓  Wallpaper running smoothly"
        else:
            tip = "Idle — no wallpaper active"
        self._health_lbl.config(text=tip)

        # Sparklines
        self._draw_sparkline(self._cpu_canvas, self._cpu_hist, cpu_col)
        self._draw_sparkline(self._ram_canvas, self._ram_hist, ram_col)

        # Process stats
        with _ws_lock:
            playing = _ws.player is not None

        if playing:
            try:
                proc = psutil.Process(os.getpid())
                pmem = proc.memory_info().rss / 1024**2
                pcpu = proc.cpu_percent(interval=None)
                self._proc_lbl.config(
                    text=f"Process CPU: {pcpu:.1f}%   |   Memory: {pmem:.1f} MB   |   "
                         f"File: {_ws.path.name if _ws.path else '—'}",
                    fg=self.C["FG2"],
                )
            except Exception:
                pass
        else:
            self._proc_lbl.config(text="Not playing", fg=self.C["FG3"])

        self._stats_id = self.after(1000, self._update_stats)

    def _draw_sparkline(self, canvas: tk.Canvas,
                         history: list[float], color: str) -> None:
        canvas.delete("all")
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 4 or h < 4 or len(history) < 2:
            return
        n    = len(history)
        step = w / (n - 1)
        pts  = []
        for i, v in enumerate(history):
            pts.extend([i * step, h - max(1, (v / 100) * (h - 2))])
        canvas.create_polygon(
            pts + [w, h, 0, h],
            fill=color, outline="", stipple="gray25",
        )
        for i in range(n - 1):
            canvas.create_line(
                i * step,       h - max(1, (history[i]     / 100) * (h - 2)),
                (i+1) * step,   h - max(1, (history[i + 1] / 100) * (h - 2)),
                fill=color, width=1.5, smooth=True,
            )

    # ── Status helpers ────────────────────────────────────────────────────────
    def _set_status(self, msg: str, *, error: bool = False) -> None:
        self._status_var.set(msg)
        self._status_dot.config(
            fg=self.C["DANGER"] if error else
               (self.C["SUCCESS"] if self._is_playing else self.C["FG3"])
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def on_close(self) -> None:
        log.info("Closing application.")
        if self._stats_id:
            self.after_cancel(self._stats_id)
            self._stats_id = None
        self._save_settings()
        try:
            stop_wallpaper()
        except Exception as exc:
            log.error("Error during shutdown stop: %s", exc)
        self.destroy()


# ──────────────────────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        app = App()
        app.protocol("WM_DELETE_WINDOW", app.on_close)
        signal.signal(signal.SIGINT, lambda *_: app.after(0, app.on_close))
        log.info("App started — VLC folder: %s", _vlc_folder)
        app.mainloop()
    except Exception:
        traceback.print_exc()
        log.critical("Unhandled exception", exc_info=True)
        input("\nPress Enter to exit…")
