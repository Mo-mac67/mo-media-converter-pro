
import os
import sys
import json
import time
import queue
import shutil
import threading
import subprocess
import urllib.request
import urllib.parse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

APP_TITLE = "Mo Media Converter Pro v3"
APP_SIZE = "1260x860"
APP_MIN_SIZE = (1120, 760)
APP_DIR = os.path.join(os.path.expanduser("~"), ".mo_media_converter_pro")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
PRESETS_FILE = os.path.join(APP_DIR, "custom_presets.json")
DOWNLOAD_HISTORY_FILE = os.path.join(APP_DIR, "download_history.json")

DND_READY = False
TkinterDnD = None
DND_FILES = None
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_READY = True
except Exception:
    DND_READY = False

INPUT_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".m4v", ".flv", ".mpeg", ".mpg", ".ts", ".mts",
    ".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".opus", ".wma", ".aiff", ".aif", ".amr"
}
AUDIO_OUTPUT_FORMATS = ["mp3", "wav", "flac", "aac", "m4a", "ogg", "opus"]
VIDEO_OUTPUT_FORMATS = ["mp4", "mkv", "mov", "webm"]

BUILTIN_PRESETS = {
    "Custom": {},
    "Music": {"output_kind":"Audio","output_format":"mp3","audio_bitrate":"320k","sample_rate":"44100","keep_video":False},
    "Voice": {"output_kind":"Audio","output_format":"mp3","audio_bitrate":"128k","sample_rate":"22050","keep_video":False},
    "YouTube Audio": {"output_kind":"Audio","output_format":"m4a","audio_bitrate":"256k","sample_rate":"44100","keep_video":False},
    "YouTube Video": {"output_kind":"Video","output_format":"mp4","video_codec":"h264","video_quality":"High","audio_bitrate":"192k","sample_rate":"44100","keep_video":True},
    "Archive Lossless": {"output_kind":"Audio","output_format":"flac","sample_rate":"48000","keep_video":False},
    "Mobile Small": {"output_kind":"Video","output_format":"mp4","video_codec":"h264","video_quality":"Balanced","audio_bitrate":"128k","sample_rate":"44100","keep_video":True},
}

AUDIO_BITRATES = ["64k", "96k", "128k", "160k", "192k", "256k", "320k"]
SAMPLE_RATES = ["22050", "32000", "44100", "48000"]
VIDEO_QUALITIES = ["Small", "Balanced", "High", "Very High"]
VIDEO_CODECS = ["h264", "hevc", "vp9"]

CONTAINER_BY_FORMAT = {
    "mp3": "mp3", "wav": "wav", "flac": "flac", "aac": "adts", "m4a": "ipod", "ogg": "ogg", "opus": "opus",
    "mp4": "mp4", "mkv": "matroska", "mov": "mov", "webm": "webm",
}

COLORS = {
    "bg": "#0f1115",
    "panel": "#161a22",
    "panel2": "#1b2130",
    "panel3": "#10141c",
    "text": "#e5e7eb",
    "muted": "#9ca3af",
    "line": "#2a3242",
    "accent": "#4f8cff",
    "accent2": "#79a7ff",
    "green": "#10b981",
    "orange": "#f59e0b",
    "red": "#ef4444",
}

HELP_TEXT = """\
MO MEDIA CONVERTER PRO v3

NEW IN v3
- Direct URL downloader for public file links
- Download history
- Download tab can add downloaded file straight into converter queue
- Legal-use disclaimer inside app

IMPORTANT
This downloader is for direct, public, authorized file URLs only.
Do not use it to infringe copyright, bypass platform restrictions,
or download media you do not have the right to access.

REQUIREMENTS
1) Python 3.10+ recommended
2) FFmpeg installed:
   winget install ffmpeg

OPTIONAL
Drag & Drop:
   python -m pip install tkinterdnd2

RUN
   python mo_media_converter_pro_v3.py

BUILD EXE
   python -m pip install pyinstaller
   pyinstaller --noconsole --onefile mo_media_converter_pro_v3.py

OPTIONAL ICON
   pyinstaller --noconsole --onefile --icon youricon.ico mo_media_converter_pro_v3.py
"""

def ensure_app_dir():
    os.makedirs(APP_DIR, exist_ok=True)

def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def write_json(path, data):
    ensure_app_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def safe_startfile(path):
    try:
        os.startfile(path)
    except Exception:
        pass

def format_seconds(seconds):
    if seconds is None:
        return "Unknown"
    try:
        seconds = max(0, int(float(seconds)))
    except Exception:
        return "Unknown"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def parse_drop_files(data):
    files = []
    current = ""
    in_brace = False
    for ch in data:
        if ch == "{":
            in_brace = True
            current = ""
        elif ch == "}":
            in_brace = False
            if current:
                files.append(current)
                current = ""
        elif ch == " " and not in_brace:
            if current:
                files.append(current)
                current = ""
        else:
            current += ch
    if current:
        files.append(current)
    return [f.strip() for f in files if f.strip()]

def find_ff_tools():
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    c1 = os.path.join(local_appdata, "Microsoft", "WinGet", "Links", "ffmpeg.exe")
    c2 = os.path.join(local_appdata, "Microsoft", "WinGet", "Links", "ffprobe.exe")
    if not ffmpeg and os.path.exists(c1):
        ffmpeg = c1
    if not ffprobe and os.path.exists(c2):
        ffprobe = c2
    return ffmpeg, ffprobe

def probe_media(ffprobe_path, input_path):
    cmd = [
        ffprobe_path, "-v", "error",
        "-show_entries", "format=duration:stream=index,codec_type,codec_name,width,height",
        "-of", "json", input_path
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        data = json.loads(result.stdout)
        duration = None
        width = height = None
        has_video = False
        has_audio = False
        for s in data.get("streams", []):
            if s.get("codec_type") == "video":
                has_video = True
                width = s.get("width")
                height = s.get("height")
            elif s.get("codec_type") == "audio":
                has_audio = True
        try:
            duration = float(data.get("format", {}).get("duration"))
        except Exception:
            duration = None
        return {"duration": duration, "has_video": has_video, "has_audio": has_audio, "width": width, "height": height}
    except Exception:
        return {"duration": None, "has_video": False, "has_audio": False, "width": None, "height": None}

class DownloadWorker(threading.Thread):
    def __init__(self, url, target_path, q, add_to_queue=False):
        super().__init__(daemon=True)
        self.url = url
        self.target_path = target_path
        self.q = q
        self.add_to_queue = add_to_queue
        self.cancel_requested = False

    def run(self):
        tmp_path = self.target_path + ".part"
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                total = r.headers.get("Content-Length")
                total = int(total) if total and total.isdigit() else None
                downloaded = 0
                chunk_size = 1024 * 128
                start = time.time()
                with open(tmp_path, "wb") as f:
                    while True:
                        if self.cancel_requested:
                            raise RuntimeError("Download cancelled")
                        chunk = r.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        pct = (downloaded / total * 100.0) if total else 0.0
                        elapsed = max(0.001, time.time() - start)
                        speed = downloaded / elapsed
                        eta = ((total - downloaded) / speed) if total and speed > 0 else None
                        self.q.put(("download_progress", (pct, downloaded, total, eta)))
            if os.path.exists(self.target_path):
                os.remove(self.target_path)
            os.replace(tmp_path, self.target_path)
            self.q.put(("download_done", {"path": self.target_path, "add_to_queue": self.add_to_queue, "url": self.url}))
        except Exception as e:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            self.q.put(("download_error", str(e)))

    def cancel(self):
        self.cancel_requested = True

class ConverterApp:
    def __init__(self, root):
        self.root = root
        ensure_app_dir()
        self.ffmpeg_path, self.ffprobe_path = find_ff_tools()
        self.jobs = []
        self.log_queue = queue.Queue()
        self.cancel_requested = False
        self.convert_thread = None
        self.active_process = None
        self.download_worker = None
        self.custom_presets = read_json(PRESETS_FILE, {})
        self.last_settings = read_json(SETTINGS_FILE, {})
        self.download_history = read_json(DOWNLOAD_HISTORY_FILE, [])

        self.output_kind_var = tk.StringVar(value="Audio")
        self.output_format_var = tk.StringVar(value="mp3")
        self.preset_var = tk.StringVar(value="Music")
        self.audio_bitrate_var = tk.StringVar(value="320k")
        self.sample_rate_var = tk.StringVar(value="44100")
        self.video_codec_var = tk.StringVar(value="h264")
        self.video_quality_var = tk.StringVar(value="High")
        self.output_mode_var = tk.StringVar(value="folder")
        self.output_dir_var = tk.StringVar(value=os.path.join(os.getcwd(), "converted"))
        self.open_folder_after_var = tk.BooleanVar(value=True)
        self.skip_existing_var = tk.BooleanVar(value=True)
        self.overwrite_var = tk.BooleanVar(value=True)
        self.keep_video_var = tk.BooleanVar(value=False)

        self.status_var = tk.StringVar(value="Ready")
        self.current_file_var = tk.StringVar(value="No active job")
        self.summary_var = tk.StringVar(value="0 file(s) queued")
        self.ff_status_var = tk.StringVar(value="")
        self.hint_var = tk.StringVar(value="Drop files here or use Add Files / Add Folder")
        self.eta_var = tk.StringVar(value="ETA: --:--:--")

        self.url_var = tk.StringVar()
        self.download_name_var = tk.StringVar()
        self.download_folder_var = tk.StringVar(value=os.path.join(os.getcwd(), "downloads"))
        self.download_status_var = tk.StringVar(value="Downloader idle")
        self.download_eta_var = tk.StringVar(value="Download ETA: --:--:--")
        self.add_download_to_queue_var = tk.BooleanVar(value=True)
        self.legal_ack_var = tk.BooleanVar(value=False)

        self.file_progress = tk.DoubleVar(value=0)
        self.total_progress = tk.DoubleVar(value=0)
        self.download_progress = tk.DoubleVar(value=0)

        self._setup_window()
        self._build_style()
        self._build_ui()
        self.load_settings_to_ui()
        self.refresh_presets()
        self.refresh_ff_status()
        self.refresh_download_history()
        self.poll_queue()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _setup_window(self):
        self.root.title(APP_TITLE)
        self.root.geometry(APP_SIZE)
        self.root.minsize(*APP_MIN_SIZE)
        self.root.configure(bg=COLORS["bg"])

    def _build_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["panel"])
        style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI", 20, "bold"))
        style.configure("Sub.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI", 11, "bold"))
        style.configure("CardText.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("Eta.TLabel", background=COLORS["panel"], foreground=COLORS["green"], font=("Segoe UI", 9, "bold"))
        style.configure("Warn.TLabel", background=COLORS["panel"], foreground=COLORS["orange"], font=("Segoe UI", 9, "bold"))
        style.configure("Status.TLabel", background=COLORS["panel"], foreground=COLORS["accent"], font=("Segoe UI", 9, "bold"))
        style.configure("Accent.TButton", background=COLORS["accent"], foreground="white", borderwidth=0, padding=10, font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", COLORS["accent2"])])
        style.configure("Soft.TButton", background=COLORS["panel2"], foreground=COLORS["text"], borderwidth=0, padding=9, font=("Segoe UI", 10))
        style.map("Soft.TButton", background=[("active", COLORS["line"])])
        style.configure("Treeview", background=COLORS["panel3"], foreground=COLORS["text"], fieldbackground=COLORS["panel3"], rowheight=28, bordercolor=COLORS["line"])
        style.configure("Treeview.Heading", background=COLORS["panel2"], foreground=COLORS["text"], relief="flat", font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", COLORS["accent"])], foreground=[("selected", "white")])
        style.configure("TCheckbutton", background=COLORS["panel"], foreground=COLORS["text"])
        style.configure("TRadiobutton", background=COLORS["panel"], foreground=COLORS["text"])
        style.configure("TCombobox", fieldbackground=COLORS["panel3"], background=COLORS["panel3"], foreground=COLORS["text"], arrowcolor=COLORS["text"])
        style.configure("TEntry", fieldbackground=COLORS["panel3"], foreground=COLORS["text"])
        style.configure("Horizontal.TProgressbar", thickness=14, troughcolor=COLORS["panel3"], background=COLORS["accent"], bordercolor=COLORS["line"], lightcolor=COLORS["accent"], darkcolor=COLORS["accent"])

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Mo Media Converter Pro v3", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Offline converter + direct public-file downloader • personal/home use workflow", style="Sub.TLabel").pack(anchor="w", pady=(4, 0))

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True)

        self.tab_convert = ttk.Frame(self.notebook)
        self.tab_download = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_convert, text="Converter")
        self.notebook.add(self.tab_download, text="Download from URL")

        self._build_converter_tab()
        self._build_downloader_tab()

    def _build_converter_tab(self):
        content = ttk.Frame(self.tab_convert, padding=4)
        content.pack(fill="both", expand=True)

        left = ttk.Frame(content)
        left.pack(side="left", fill="both", expand=True)

        right = ttk.Frame(content, width=350)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)

        self.build_drop_zone(left)
        self.build_queue_card(left)
        self.build_progress_card(left)

        self.build_settings_card(right)
        self.build_actions_card(right)
        self.build_log_card(right)

    def _build_downloader_tab(self):
        wrap = ttk.Frame(self.tab_download, padding=12)
        wrap.pack(fill="both", expand=True)

        left = ttk.Frame(wrap)
        left.pack(side="left", fill="both", expand=True)

        right = ttk.Frame(wrap, width=360)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)

        card = ttk.Frame(left, style="Card.TFrame", padding=14)
        card.pack(fill="x")

        ttk.Label(card, text="Direct URL Downloader", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="Use only for direct, public, authorized file URLs.", style="Warn.TLabel").pack(anchor="w", pady=(6, 10))

        self._entry_row(card, "File URL", self.url_var)
        self._entry_row(card, "Save as (optional)", self.download_name_var)
        self._entry_row(card, "Download folder", self.download_folder_var, browse=True, browse_cmd=self.choose_download_dir)

        ttk.Checkbutton(card, text="Add downloaded file to converter queue automatically", variable=self.add_download_to_queue_var).pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(card, text="I understand this must not be used to infringe copyright or bypass restrictions", variable=self.legal_ack_var).pack(anchor="w", pady=(6, 0))

        buttons = ttk.Frame(card, style="Card.TFrame")
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Start Download", style="Accent.TButton", command=self.start_download).pack(side="left")
        ttk.Button(buttons, text="Cancel Download", style="Soft.TButton", command=self.cancel_download).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Open Download Folder", style="Soft.TButton", command=lambda: safe_startfile(self.download_folder_var.get().strip() or os.getcwd())).pack(side="left", padx=(8, 0))

        prog = ttk.Frame(left, style="Card.TFrame", padding=14)
        prog.pack(fill="x", pady=(12, 0))
        ttk.Label(prog, text="Download Progress", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(prog, textvariable=self.download_status_var, style="CardText.TLabel").pack(anchor="w", pady=(8, 4))
        ttk.Progressbar(prog, variable=self.download_progress, maximum=100).pack(fill="x")
        ttk.Label(prog, textvariable=self.download_eta_var, style="Eta.TLabel").pack(anchor="w", pady=(6, 0))

        hist = ttk.Frame(left, style="Card.TFrame", padding=14)
        hist.pack(fill="both", expand=True, pady=(12, 0))
        top = ttk.Frame(hist, style="Card.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="Download History", style="CardTitle.TLabel").pack(side="left")
        ttk.Button(top, text="Clear History", style="Soft.TButton", command=self.clear_download_history).pack(side="right")

        self.history_list = tk.Listbox(
            hist, bg=COLORS["panel3"], fg=COLORS["text"], selectbackground=COLORS["accent"],
            selectforeground="white", relief="flat", bd=0, font=("Consolas", 9)
        )
        self.history_list.pack(fill="both", expand=True, pady=(10, 0))

        side = ttk.Frame(right, style="Card.TFrame", padding=14)
        side.pack(fill="both", expand=True)
        ttk.Label(side, text="Notes", style="CardTitle.TLabel").pack(anchor="w")
        notes = (
            "This downloader handles direct file URLs such as public MP3, MP4, WAV, M4A, ZIP, or similar files.\n\n"
            "It is not a site-ripping tool and is not intended to bypass platform controls.\n\n"
            "Typical good use cases:\n"
            "- Your own hosted media files\n"
            "- Public podcast/media URLs\n"
            "- Direct asset links from your own server/CDN\n"
            "- Authorized downloads\n\n"
            "After download, the file can be sent into the Converter queue automatically."
        )
        tk.Label(side, text=notes, justify="left", wraplength=300, bg=COLORS["panel"], fg=COLORS["muted"], font=("Segoe UI", 10)).pack(anchor="w", pady=(10, 0))

    def _entry_row(self, parent, label, var, browse=False, browse_cmd=None):
        box = ttk.Frame(parent, style="Card.TFrame")
        box.pack(fill="x", pady=(0, 8))
        ttk.Label(box, text=label, style="CardText.TLabel").pack(anchor="w")
        row = ttk.Frame(box, style="Card.TFrame")
        row.pack(fill="x", pady=(4, 0))
        entry = ttk.Entry(row, textvariable=var)
        entry.pack(side="left", fill="x", expand=True)
        if browse:
            ttk.Button(row, text="Browse", style="Soft.TButton", command=browse_cmd).pack(side="left", padx=(8, 0))

    def build_drop_zone(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="x", pady=(0, 12))
        top = ttk.Frame(card, style="Card.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="Quick Add", style="CardTitle.TLabel").pack(side="left")
        ttk.Label(top, text=("Drag & Drop: Enabled" if DND_READY else "Drag & Drop: install tkinterdnd2"), style="Muted.TLabel").pack(side="right")

        self.drop_frame = tk.Frame(card, bg=COLORS["panel2"], highlightthickness=1, highlightbackground=COLORS["line"], bd=0, height=86)
        self.drop_frame.pack(fill="x", pady=(10, 8))
        self.drop_label = tk.Label(self.drop_frame, textvariable=self.hint_var, bg=COLORS["panel2"], fg=COLORS["text"], font=("Segoe UI", 11, "bold"))
        self.drop_label.place(relx=0.5, rely=0.5, anchor="center")

        btns = ttk.Frame(card, style="Card.TFrame")
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text="Add Files", style="Soft.TButton", command=self.add_files).pack(side="left")
        ttk.Button(btns, text="Add Folder", style="Soft.TButton", command=self.add_folder).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Remove Selected", style="Soft.TButton", command=self.remove_selected).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Clear Queue", style="Soft.TButton", command=self.clear_queue).pack(side="left", padx=(8, 0))

        if DND_READY:
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind("<<Drop>>", self.on_drop)
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind("<<Drop>>", self.on_drop)

    def build_queue_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="both", expand=True)
        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill="x")
        ttk.Label(row, text="Queue", style="CardTitle.TLabel").pack(side="left")
        ttk.Label(row, textvariable=self.summary_var, style="Muted.TLabel").pack(side="right")

        columns = ("name", "kind", "duration", "resolution", "status", "target")
        self.tree = ttk.Treeview(card, columns=columns, show="headings", selectmode="extended")
        self.tree.pack(fill="both", expand=True, pady=(10, 0))
        titles = {"name":"Source File", "kind":"Type", "duration":"Duration", "resolution":"Resolution", "status":"Status", "target":"Output"}
        widths = {"name":360, "kind":90, "duration":100, "resolution":110, "status":110, "target":110}
        for c in columns:
            self.tree.heading(c, text=titles[c])
            self.tree.column(c, width=widths[c], anchor="center" if c != "name" else "w")

    def build_progress_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="x", pady=(12, 0))
        ttk.Label(card, text="Progress", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, textvariable=self.current_file_var, style="CardText.TLabel").pack(anchor="w", pady=(8, 4))
        ttk.Progressbar(card, variable=self.file_progress, maximum=100).pack(fill="x")
        self.file_progress_label = ttk.Label(card, text="Current file: 0.0%", style="Muted.TLabel")
        self.file_progress_label.pack(anchor="w", pady=(6, 6))
        ttk.Label(card, textvariable=self.eta_var, style="Eta.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Progressbar(card, variable=self.total_progress, maximum=100).pack(fill="x")
        self.total_progress_label = ttk.Label(card, text="Queue: 0.0%", style="Muted.TLabel")
        self.total_progress_label.pack(anchor="w", pady=(6, 0))

    def build_settings_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="x")
        ttk.Label(card, text="Settings", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))

        self._add_combo(card, "Preset", self.preset_var, [], self.on_preset_change)
        btnrow = ttk.Frame(card, style="Card.TFrame")
        btnrow.pack(fill="x", pady=(0, 8))
        ttk.Button(btnrow, text="Save Preset", style="Soft.TButton", command=self.save_current_preset).pack(side="left")
        ttk.Button(btnrow, text="Delete Preset", style="Soft.TButton", command=self.delete_current_preset).pack(side="left", padx=(8, 0))

        self._add_combo(card, "Output type", self.output_kind_var, ["Audio", "Video"], self.on_output_kind_change)
        self._add_combo(card, "Output format", self.output_format_var, AUDIO_OUTPUT_FORMATS, None)
        self._add_combo(card, "Audio bitrate", self.audio_bitrate_var, AUDIO_BITRATES, None)
        self._add_combo(card, "Sample rate", self.sample_rate_var, SAMPLE_RATES, None)
        self._add_combo(card, "Video codec", self.video_codec_var, VIDEO_CODECS, None)
        self._add_combo(card, "Video quality", self.video_quality_var, VIDEO_QUALITIES, None)

        mode_row = ttk.Frame(card, style="Card.TFrame")
        mode_row.pack(fill="x", pady=(6, 6))
        ttk.Label(mode_row, text="Output location", style="CardText.TLabel").pack(anchor="w")
        line = ttk.Frame(mode_row, style="Card.TFrame")
        line.pack(fill="x", pady=(4, 0))
        ttk.Radiobutton(line, text="Same folder", variable=self.output_mode_var, value="same", command=self.toggle_output_dir).pack(side="left")
        ttk.Radiobutton(line, text="Custom folder", variable=self.output_mode_var, value="folder", command=self.toggle_output_dir).pack(side="left", padx=(10, 0))

        outrow = ttk.Frame(card, style="Card.TFrame")
        outrow.pack(fill="x", pady=(4, 8))
        self.output_entry = ttk.Entry(outrow, textvariable=self.output_dir_var)
        self.output_entry.pack(side="left", fill="x", expand=True)
        self.output_browse = ttk.Button(outrow, text="Browse", style="Soft.TButton", command=self.choose_output_dir)
        self.output_browse.pack(side="left", padx=(8, 0))

        ttk.Checkbutton(card, text="Skip if target exists", variable=self.skip_existing_var).pack(anchor="w")
        ttk.Checkbutton(card, text="Overwrite target when needed", variable=self.overwrite_var).pack(anchor="w")
        ttk.Checkbutton(card, text="Open output folder when finished", variable=self.open_folder_after_var).pack(anchor="w")
        ttk.Checkbutton(card, text="Keep video when output type is Video", variable=self.keep_video_var).pack(anchor="w")

        self.toggle_video_controls()
        self.toggle_output_dir()

    def build_actions_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="x", pady=(12, 0))
        ttk.Label(card, text="Actions", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Button(card, text="Start Conversion", style="Accent.TButton", command=self.start_conversion).pack(fill="x")
        ttk.Button(card, text="Cancel Current Job", style="Soft.TButton", command=self.cancel_conversion).pack(fill="x", pady=(8, 0))
        ttk.Button(card, text="Open Output Folder", style="Soft.TButton", command=self.open_output_folder).pack(fill="x", pady=(8, 0))
        ttk.Button(card, text="Help / Setup", style="Soft.TButton", command=self.show_help).pack(fill="x", pady=(8, 0))
        ttk.Button(card, text="Open App Data Folder", style="Soft.TButton", command=lambda: safe_startfile(APP_DIR)).pack(fill="x", pady=(8, 0))
        ttk.Separator(card, orient="horizontal").pack(fill="x", pady=12)
        ttk.Label(card, textvariable=self.ff_status_var, style="Muted.TLabel", wraplength=300, justify="left").pack(anchor="w")
        ttk.Label(card, textvariable=self.status_var, style="Status.TLabel", wraplength=300, justify="left").pack(anchor="w", pady=(8, 0))

    def build_log_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="both", expand=True, pady=(12, 0))
        ttk.Label(card, text="Log", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))
        self.log_text = tk.Text(card, height=10, wrap="word", bg=COLORS["panel3"], fg=COLORS["text"], insertbackground=COLORS["text"], font=("Consolas", 9), relief="flat", bd=0)
        self.log_text.pack(fill="both", expand=True)

    def _add_combo(self, parent, label, var, values, command):
        box = ttk.Frame(parent, style="Card.TFrame")
        box.pack(fill="x", pady=(0, 7))
        ttk.Label(box, text=label, style="CardText.TLabel").pack(anchor="w")
        cb = ttk.Combobox(box, textvariable=var, values=values, state="readonly")
        cb.pack(fill="x", pady=(4, 0))
        if command:
            cb.bind("<<ComboboxSelected>>", command)
        setattr(self, f"combo_{label.lower().replace(' ', '_')}", cb)

    def load_settings_to_ui(self):
        s = self.last_settings
        self.output_kind_var.set(s.get("output_kind", "Audio"))
        self.output_format_var.set(s.get("output_format", "mp3"))
        self.preset_var.set(s.get("preset", "Music"))
        self.audio_bitrate_var.set(s.get("audio_bitrate", "320k"))
        self.sample_rate_var.set(s.get("sample_rate", "44100"))
        self.video_codec_var.set(s.get("video_codec", "h264"))
        self.video_quality_var.set(s.get("video_quality", "High"))
        self.output_mode_var.set(s.get("output_mode", "folder"))
        self.output_dir_var.set(s.get("output_dir", os.path.join(os.getcwd(), "converted")))
        self.open_folder_after_var.set(s.get("open_folder_after", True))
        self.skip_existing_var.set(s.get("skip_existing", True))
        self.overwrite_var.set(s.get("overwrite", True))
        self.keep_video_var.set(s.get("keep_video", False))
        self.download_folder_var.set(s.get("download_folder", os.path.join(os.getcwd(), "downloads")))
        self.add_download_to_queue_var.set(s.get("add_download_to_queue", True))

    def collect_settings(self):
        return {
            "output_kind": self.output_kind_var.get(),
            "output_format": self.output_format_var.get(),
            "preset": self.preset_var.get(),
            "audio_bitrate": self.audio_bitrate_var.get(),
            "sample_rate": self.sample_rate_var.get(),
            "video_codec": self.video_codec_var.get(),
            "video_quality": self.video_quality_var.get(),
            "output_mode": self.output_mode_var.get(),
            "output_dir": self.output_dir_var.get(),
            "open_folder_after": self.open_folder_after_var.get(),
            "skip_existing": self.skip_existing_var.get(),
            "overwrite": self.overwrite_var.get(),
            "keep_video": self.keep_video_var.get(),
            "download_folder": self.download_folder_var.get(),
            "add_download_to_queue": self.add_download_to_queue_var.get(),
        }

    def save_settings(self):
        write_json(SETTINGS_FILE, self.collect_settings())

    def refresh_presets(self):
        merged = list(BUILTIN_PRESETS.keys()) + sorted(self.custom_presets.keys())
        self.combo_preset.configure(values=merged)
        if self.preset_var.get() not in merged:
            self.preset_var.set("Music")

    def refresh_ff_status(self):
        if self.ffmpeg_path and self.ffprobe_path:
            extra = "Drag & Drop ready" if DND_READY else "Install tkinterdnd2 for drag & drop"
            self.ff_status_var.set(f"FFmpeg detected.\n{self.ffmpeg_path}\n{extra}")
        else:
            self.ff_status_var.set("FFmpeg / FFprobe not found.\nInstall with: winget install ffmpeg")

    def refresh_download_history(self):
        self.history_list.delete(0, "end")
        for item in reversed(self.download_history[-200:]):
            self.history_list.insert("end", f"{item.get('time','')} | {os.path.basename(item.get('path',''))} | {item.get('url','')}")

    def clear_download_history(self):
        self.download_history = []
        write_json(DOWNLOAD_HISTORY_FILE, self.download_history)
        self.refresh_download_history()

    def show_help(self):
        messagebox.showinfo("Help / Setup", HELP_TEXT)

    def on_drop(self, event):
        files = parse_drop_files(event.data)
        files = [f for f in files if os.path.exists(f)]
        if files:
            self.add_job_paths(files)

    def on_preset_change(self, _=None):
        name = self.preset_var.get()
        preset = BUILTIN_PRESETS.get(name, self.custom_presets.get(name, {}))
        if not preset:
            return
        for k, v in preset.items():
            if k == "output_kind":
                self.output_kind_var.set(v)
            elif k == "output_format":
                self.output_format_var.set(v)
            elif k == "audio_bitrate":
                self.audio_bitrate_var.set(v)
            elif k == "sample_rate":
                self.sample_rate_var.set(v)
            elif k == "video_codec":
                self.video_codec_var.set(v)
            elif k == "video_quality":
                self.video_quality_var.set(v)
            elif k == "keep_video":
                self.keep_video_var.set(bool(v))
        self.on_output_kind_change()

    def save_current_preset(self):
        name = simpledialog.askstring("Save Preset", "Preset name:", parent=self.root)
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if name in BUILTIN_PRESETS:
            messagebox.showwarning(APP_TITLE, "That preset name is reserved by a built-in preset.")
            return
        self.custom_presets[name] = {
            "output_kind": self.output_kind_var.get(),
            "output_format": self.output_format_var.get(),
            "audio_bitrate": self.audio_bitrate_var.get(),
            "sample_rate": self.sample_rate_var.get(),
            "video_codec": self.video_codec_var.get(),
            "video_quality": self.video_quality_var.get(),
            "keep_video": self.keep_video_var.get(),
        }
        write_json(PRESETS_FILE, self.custom_presets)
        self.refresh_presets()
        self.preset_var.set(name)
        self.log(f"Saved preset: {name}")

    def delete_current_preset(self):
        name = self.preset_var.get()
        if name in BUILTIN_PRESETS:
            messagebox.showinfo(APP_TITLE, "Built-in presets cannot be deleted.")
            return
        if name not in self.custom_presets:
            return
        if not messagebox.askyesno(APP_TITLE, f"Delete preset '{name}'?"):
            return
        del self.custom_presets[name]
        write_json(PRESETS_FILE, self.custom_presets)
        self.refresh_presets()
        self.preset_var.set("Music")
        self.log(f"Deleted preset: {name}")

    def on_output_kind_change(self, _=None):
        if self.output_kind_var.get() == "Audio":
            self.combo_output_format.configure(values=AUDIO_OUTPUT_FORMATS)
            if self.output_format_var.get() not in AUDIO_OUTPUT_FORMATS:
                self.output_format_var.set("mp3")
        else:
            self.combo_output_format.configure(values=VIDEO_OUTPUT_FORMATS)
            if self.output_format_var.get() not in VIDEO_OUTPUT_FORMATS:
                self.output_format_var.set("mp4")
        self.toggle_video_controls()

    def toggle_video_controls(self):
        state = "readonly" if self.output_kind_var.get() == "Video" else "disabled"
        self.combo_video_codec.configure(state=state)
        self.combo_video_quality.configure(state=state)

    def toggle_output_dir(self):
        state = "normal" if self.output_mode_var.get() == "folder" else "disabled"
        self.output_entry.configure(state=state)
        self.output_browse.configure(state=state)

    def choose_output_dir(self):
        folder = filedialog.askdirectory(title="Choose output folder")
        if folder:
            self.output_dir_var.set(folder)

    def choose_download_dir(self):
        folder = filedialog.askdirectory(title="Choose download folder")
        if folder:
            self.download_folder_var.set(folder)

    def infer_filename_from_url(self, url):
        path = urllib.parse.urlparse(url).path
        name = os.path.basename(path)
        return name or "downloaded_file"

    def start_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning(APP_TITLE, "Enter a direct file URL.")
            return
        if not self.legal_ack_var.get():
            messagebox.showwarning(APP_TITLE, "Please confirm the legal-use disclaimer first.")
            return
        if self.download_worker and self.download_worker.is_alive():
            messagebox.showinfo(APP_TITLE, "A download is already running.")
            return

        folder = self.download_folder_var.get().strip() or os.path.join(os.getcwd(), "downloads")
        os.makedirs(folder, exist_ok=True)

        name = self.download_name_var.get().strip() or self.infer_filename_from_url(url)
        target_path = os.path.join(folder, name)

        self.download_progress.set(0)
        self.download_status_var.set(f"Downloading {name}")
        self.download_eta_var.set("Download ETA: --:--:--")
        self.log(f"Starting download: {url}")

        self.download_worker = DownloadWorker(url, target_path, self.log_queue, self.add_download_to_queue_var.get())
        self.download_worker.start()
        self.save_settings()

    def cancel_download(self):
        if self.download_worker and self.download_worker.is_alive():
            self.download_worker.cancel()
            self.download_status_var.set("Cancelling download...")
            self.log("Download cancellation requested.")

    def add_files(self):
        filetypes = [("Media files", " ".join(f"*{ext}" for ext in sorted(INPUT_EXTENSIONS))), ("All files", "*.*")]
        paths = filedialog.askopenfilenames(title="Select media files", filetypes=filetypes)
        if paths:
            self.add_job_paths(paths)

    def add_folder(self):
        folder = filedialog.askdirectory(title="Select folder")
        if not folder:
            return
        found = []
        for root, _, files in os.walk(folder):
            for name in files:
                p = os.path.join(root, name)
                if os.path.splitext(name)[1].lower() in INPUT_EXTENSIONS:
                    found.append(p)
        if found:
            self.add_job_paths(found)
        else:
            messagebox.showinfo(APP_TITLE, "No supported media files found in that folder.")

    def add_job_paths(self, paths):
        existing = {job["input_path"] for job in self.jobs}
        added = 0
        for path in paths:
            if not os.path.isfile(path):
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext not in INPUT_EXTENSIONS or path in existing:
                continue
            meta = probe_media(self.ffprobe_path, path) if self.ffprobe_path else {"duration":None,"has_video":False,"has_audio":False,"width":None,"height":None}
            kind = "Video" if meta["has_video"] else "Audio"
            res = f'{meta["width"]}x{meta["height"]}' if meta["width"] and meta["height"] else "-"
            item_id = self.tree.insert("", "end", values=(os.path.basename(path), kind, format_seconds(meta["duration"]), res, "Queued", self.output_format_var.get().upper()))
            self.jobs.append({"item_id": item_id, "input_path": path, "meta": meta})
            added += 1
        self.update_summary()
        if added:
            self.log(f"Added {added} file(s).")

    def remove_selected(self):
        selected = set(self.tree.selection())
        if not selected:
            return
        self.jobs = [job for job in self.jobs if job["item_id"] not in selected]
        for item_id in selected:
            self.tree.delete(item_id)
        self.update_summary()
        self.log(f"Removed {len(selected)} item(s).")

    def clear_queue(self):
        if self.convert_thread and self.convert_thread.is_alive():
            messagebox.showwarning(APP_TITLE, "Cannot clear the queue while conversion is running.")
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.jobs.clear()
        self.file_progress.set(0)
        self.total_progress.set(0)
        self.current_file_var.set("No active job")
        self.eta_var.set("ETA: --:--:--")
        self.update_summary()
        self.log("Queue cleared.")

    def update_summary(self):
        self.summary_var.set(f"{len(self.jobs)} file(s) queued")

    def log(self, message):
        self.log_queue.put(("log", message))

    def poll_queue(self):
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "log":
                    self.log_text.insert("end", payload + "\n")
                    self.log_text.see("end")
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "current":
                    self.current_file_var.set(payload)
                elif kind == "file_progress":
                    self.file_progress.set(payload)
                    self.file_progress_label.configure(text=f"Current file: {payload:.1f}%")
                elif kind == "total_progress":
                    self.total_progress.set(payload)
                    self.total_progress_label.configure(text=f"Queue: {payload:.1f}%")
                elif kind == "eta":
                    self.eta_var.set(payload)
                elif kind == "tree_status":
                    item_id, status, target = payload
                    values = list(self.tree.item(item_id, "values"))
                    if values:
                        values[4] = status
                        if target is not None:
                            values[5] = target
                        self.tree.item(item_id, values=values)
                elif kind == "download_progress":
                    pct, downloaded, total, eta = payload
                    self.download_progress.set(pct)
                    if total:
                        self.download_status_var.set(f"Downloading... {downloaded/1048576:.1f} MB / {total/1048576:.1f} MB")
                    else:
                        self.download_status_var.set(f"Downloading... {downloaded/1048576:.1f} MB")
                    self.download_eta_var.set(f"Download ETA: {format_seconds(eta) if eta is not None else '--:--:--'}")
                elif kind == "download_done":
                    path = payload["path"]
                    self.download_progress.set(100.0)
                    self.download_status_var.set(f"Download complete: {os.path.basename(path)}")
                    self.download_eta_var.set("Download ETA: --:--:--")
                    self.download_history.append({
                        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "url": payload["url"],
                        "path": path
                    })
                    write_json(DOWNLOAD_HISTORY_FILE, self.download_history)
                    self.refresh_download_history()
                    self.log(f"Download finished: {path}")
                    if payload.get("add_to_queue"):
                        self.add_job_paths([path])
                elif kind == "download_error":
                    self.download_status_var.set(f"Download failed: {payload}")
                    self.download_eta_var.set("Download ETA: --:--:--")
                    self.log(f"Download failed: {payload}")
        except queue.Empty:
            pass
        self.root.after(120, self.poll_queue)

    def resolve_output_dir(self, input_path):
        if self.output_mode_var.get() == "same":
            return os.path.dirname(input_path)
        out = self.output_dir_var.get().strip() or os.path.join(os.getcwd(), "converted")
        os.makedirs(out, exist_ok=True)
        return out

    def build_output_path(self, input_path):
        folder = self.resolve_output_dir(input_path)
        base = os.path.splitext(os.path.basename(input_path))[0]
        ext = self.output_format_var.get().lower()
        return os.path.join(folder, f"{base}.{ext}")

    def open_output_folder(self):
        folder = self.resolve_output_dir(self.jobs[0]["input_path"] if self.jobs else os.getcwd())
        os.makedirs(folder, exist_ok=True)
        safe_startfile(folder)

    def start_conversion(self):
        if not self.ffmpeg_path or not self.ffprobe_path:
            messagebox.showerror(APP_TITLE, "FFmpeg / FFprobe not found.\nInstall with:\nwinget install ffmpeg")
            return
        if not self.jobs:
            messagebox.showinfo(APP_TITLE, "No files in queue.")
            return
        if self.convert_thread and self.convert_thread.is_alive():
            messagebox.showinfo(APP_TITLE, "Conversion is already running.")
            return
        self.save_settings()
        self.cancel_requested = False
        self.convert_thread = threading.Thread(target=self.convert_worker, daemon=True)
        self.convert_thread.start()

    def cancel_conversion(self):
        self.cancel_requested = True
        if self.active_process and self.active_process.poll() is None:
            try:
                self.active_process.terminate()
            except Exception:
                pass
        self.log("Cancellation requested.")

    def build_command(self, input_path, output_path, meta):
        output_kind = self.output_kind_var.get()
        output_format = self.output_format_var.get().lower()
        audio_bitrate = self.audio_bitrate_var.get()
        sample_rate = self.sample_rate_var.get()
        video_codec = self.video_codec_var.get()
        video_quality = self.video_quality_var.get()

        cmd = [self.ffmpeg_path]
        cmd += ["-y" if self.overwrite_var.get() else "-n"]
        cmd += ["-i", input_path]

        if output_kind == "Audio":
            cmd += ["-vn"]
            if output_format == "mp3":
                cmd += ["-c:a", "libmp3lame", "-b:a", audio_bitrate]
            elif output_format == "wav":
                cmd += ["-c:a", "pcm_s16le"]
            elif output_format == "flac":
                cmd += ["-c:a", "flac"]
            elif output_format == "aac":
                cmd += ["-c:a", "aac", "-b:a", audio_bitrate]
            elif output_format == "m4a":
                cmd += ["-c:a", "aac", "-b:a", audio_bitrate, "-f", "ipod"]
            elif output_format == "ogg":
                cmd += ["-c:a", "libvorbis", "-b:a", audio_bitrate, "-f", "ogg"]
            elif output_format == "opus":
                cmd += ["-c:a", "libopus", "-b:a", audio_bitrate, "-f", "opus"]
            if output_format not in {"flac"}:
                cmd += ["-ar", sample_rate]
        else:
            if video_codec == "h264":
                cmd += ["-c:v", "libx264"]
            elif video_codec == "hevc":
                cmd += ["-c:v", "libx265"]
            else:
                cmd += ["-c:v", "libvpx-vp9"]
            crf_map = {"Small":"32", "Balanced":"26", "High":"21", "Very High":"18"}
            cmd += ["-crf", crf_map.get(video_quality, "21"), "-preset", "medium"]
            if meta.get("has_audio"):
                if output_format == "webm":
                    cmd += ["-c:a", "libopus", "-b:a", audio_bitrate]
                else:
                    cmd += ["-c:a", "aac", "-b:a", audio_bitrate]
            else:
                cmd += ["-an"]
            if output_format == "webm" and "libvpx-vp9" not in cmd:
                for i, val in enumerate(cmd):
                    if val in ("libx264", "libx265"):
                        cmd[i] = "libvpx-vp9"
                        break

        fmt = CONTAINER_BY_FORMAT.get(output_format)
        if output_kind == "Video" and fmt:
            cmd += ["-f", fmt]
        cmd += ["-progress", "pipe:1", "-nostats", output_path]
        return cmd

    def update_eta(self, seconds_left):
        if seconds_left is None or seconds_left < 0 or seconds_left > 365*24*3600:
            self.log_queue.put(("eta", "ETA: --:--:--"))
        else:
            self.log_queue.put(("eta", f"ETA: {format_seconds(seconds_left)}"))

    def convert_worker(self):
        total = len(self.jobs)
        done = 0
        self.log_queue.put(("status", "Running"))
        queue_start = time.time()

        for job in self.jobs:
            item_id = job["item_id"]
            input_path = job["input_path"]
            meta = job["meta"]
            output_path = self.build_output_path(input_path)
            target = self.output_format_var.get().upper()

            if self.cancel_requested:
                self.log_queue.put(("tree_status", (item_id, "Cancelled", target)))
                continue

            if self.skip_existing_var.get() and os.path.exists(output_path):
                self.log_queue.put(("tree_status", (item_id, "Skipped", target)))
                self.log(f"Skipped existing: {os.path.basename(output_path)}")
                done += 1
                self.log_queue.put(("total_progress", done / total * 100))
                continue

            self.log_queue.put(("tree_status", (item_id, "Converting", target)))
            self.log_queue.put(("current", f"Converting {os.path.basename(input_path)}"))
            self.log_queue.put(("file_progress", 0.0))
            self.log(f"Starting: {os.path.basename(input_path)} -> {os.path.basename(output_path)}")

            cmd = self.build_command(input_path, output_path, meta)
            duration = meta.get("duration")
            file_start = time.time()
            last_pct = 0.0

            try:
                self.active_process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                )

                while True:
                    line = self.active_process.stdout.readline()
                    if line == "" and self.active_process.poll() is not None:
                        break
                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith("out_time_ms=") and duration and duration > 0:
                        try:
                            out_ms = int(line.split("=", 1)[1])
                            sec_done = out_ms / 1_000_000.0
                            pct = min(100.0, (sec_done / duration) * 100.0)
                            if pct >= last_pct:
                                last_pct = pct
                                self.log_queue.put(("file_progress", pct))
                                queue_pct = ((done + pct / 100.0) / total) * 100.0
                                self.log_queue.put(("total_progress", queue_pct))
                                elapsed = time.time() - file_start
                                if pct > 0 and elapsed > 0.3:
                                    speed = sec_done / elapsed
                                    if speed > 0:
                                        seconds_left_this = max(0, (duration - sec_done) / speed)
                                        remaining_full_files = total - done - 1
                                        avg_file_elapsed = (time.time() - queue_start) / max(1, done + pct / 100.0)
                                        eta_total = seconds_left_this + max(0, remaining_full_files * avg_file_elapsed)
                                        self.update_eta(eta_total)
                        except Exception:
                            pass
                    elif line.startswith("progress=") and line.endswith("end"):
                        self.log_queue.put(("file_progress", 100.0))

                return_code = self.active_process.wait()
                self.active_process = None

                if self.cancel_requested:
                    self.log_queue.put(("tree_status", (item_id, "Cancelled", target)))
                    self.log(f"Cancelled: {os.path.basename(input_path)}")
                elif return_code == 0:
                    self.log_queue.put(("tree_status", (item_id, "Done", target)))
                    self.log(f"Done: {os.path.basename(output_path)}")
                else:
                    self.log_queue.put(("tree_status", (item_id, "Failed", target)))
                    self.log(f"Failed: {os.path.basename(input_path)}")
            except Exception as e:
                self.active_process = None
                self.log_queue.put(("tree_status", (item_id, "Failed", target)))
                self.log(f"Error: {os.path.basename(input_path)} -> {e}")

            done += 1
            self.log_queue.put(("total_progress", done / total * 100))

        self.log_queue.put(("current", "No active job"))
        self.log_queue.put(("status", "Finished" if not self.cancel_requested else "Stopped"))
        self.log_queue.put(("eta", "ETA: --:--:--"))
        if self.open_folder_after_var.get() and self.jobs and not self.cancel_requested:
            safe_startfile(self.resolve_output_dir(self.jobs[0]["input_path"]))

    def on_close(self):
        self.save_settings()
        self.root.destroy()

def main():
    root = TkinterDnD.Tk() if DND_READY else tk.Tk()
    ConverterApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
