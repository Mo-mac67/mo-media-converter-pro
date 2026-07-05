
import os
import sys
import json
import time
import queue
import shutil
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

APP_TITLE = "Mo Media Converter Pro v2"
APP_SIZE = "1220x820"
APP_MIN_SIZE = (1080, 720)
APP_DIR = os.path.join(os.path.expanduser("~"), ".mo_media_converter_pro")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
PRESETS_FILE = os.path.join(APP_DIR, "custom_presets.json")

# Optional drag & drop
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
MO MEDIA CONVERTER PRO v2

WHAT'S NEW
- Saves your last-used settings automatically
- Save your own custom presets
- ETA estimate during conversion
- Better Windows-style dark UI
- Optional drag & drop
- EXE build guide included

REQUIREMENTS
1) Python 3.10+ recommended
2) FFmpeg installed:
   winget install ffmpeg

OPTIONAL
Drag & Drop:
   python -m pip install tkinterdnd2

HOW TO RUN
   python mo_media_converter_pro_v2.py

BUILD EXE
1) Install PyInstaller:
   python -m pip install pyinstaller

2) Build one-file EXE:
   pyinstaller --noconsole --onefile mo_media_converter_pro_v2.py

3) Optional custom icon:
   pyinstaller --noconsole --onefile --icon youricon.ico mo_media_converter_pro_v2.py

NOTES
- Without tkinterdnd2, the app still works. Only drag & drop is disabled.
- Your saved settings and presets are stored in:
  %USERPROFILE%\\.mo_media_converter_pro
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
        self.speed_samples = []
        self.custom_presets = read_json(PRESETS_FILE, {})
        self.last_settings = read_json(SETTINGS_FILE, {})

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

        self.file_progress = tk.DoubleVar(value=0)
        self.total_progress = tk.DoubleVar(value=0)

        self._setup_window()
        self._build_style()
        self._build_ui()
        self.load_settings_to_ui()
        self.refresh_presets()
        self.refresh_ff_status()
        self.poll_queue()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _setup_window(self):
        self.root.title(APP_TITLE)
        self.root.geometry(APP_SIZE)
        self.root.minsize(1080, 720)
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
        style.configure("Status.TLabel", background=COLORS["panel"], foreground=COLORS["accent"], font=("Segoe UI", 9, "bold"))
        style.configure("Accent.TButton", background=COLORS["accent"], foreground="white", borderwidth=0, padding=10, font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", COLORS["accent2"])])
        style.configure("Soft.TButton", background=COLORS["panel2"], foreground=COLORS["text"], borderwidth=0, padding=9, font=("Segoe UI", 10))
        style.map("Soft.TButton", background=[("active", COLORS["line"])])
        style.configure("Treeview", background=COLORS["panel3"], foreground=COLORS["text"], fieldbackground=COLORS["panel3"], rowheight=30, bordercolor=COLORS["line"])
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
        ttk.Label(header, text="Mo Media Converter Pro v2", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Offline desktop converter • saved settings • custom presets • ETA • batch queue", style="Sub.TLabel").pack(anchor="w", pady=(4, 0))

        content = ttk.Frame(outer)
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

    def show_help(self):
        messagebox.showinfo("Help / Setup", HELP_TEXT)

    def on_drop(self, event):
        files = parse_drop_files(event.data)
        files = [f for f in files if os.path.exists(f)]
        if files:
            self.add_job_paths(files)

    def on_preset_change(self, _=None):
        name = self.preset_var.get()
        if name in BUILTIN_PRESETS:
            preset = BUILTIN_PRESETS[name]
        else:
            preset = self.custom_presets.get(name, {})
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
