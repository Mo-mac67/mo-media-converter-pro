
import os
import sys
import json
import queue
import shutil
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "Home Media Converter"
APP_GEOMETRY = "980x700"

INPUT_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".m4v", ".flv", ".mpeg", ".mpg", ".ts",
    ".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".opus", ".wma", ".aiff", ".aif", ".amr"
}

OUTPUT_FORMATS = ["mp3", "wav", "flac", "aac", "m4a", "ogg"]

FORMAT_CODEC_ARGS = {
    "mp3": ["-vn", "-codec:a", "libmp3lame"],
    "wav": ["-vn", "-codec:a", "pcm_s16le"],
    "flac": ["-vn", "-codec:a", "flac"],
    "aac": ["-vn", "-codec:a", "aac"],
    "m4a": ["-vn", "-codec:a", "aac"],
    "ogg": ["-vn", "-codec:a", "libvorbis"],
}

BITRATES = ["96k", "128k", "192k", "256k", "320k"]

BG = "#f5f7fb"
CARD = "#ffffff"
TEXT = "#1f2937"
MUTED = "#6b7280"
ACCENT = "#2563eb"
ACCENT_2 = "#1d4ed8"
BORDER = "#dbe3f0"
SUCCESS = "#0f766e"
WARN = "#b45309"
DANGER = "#b91c1c"


def resource_path(relative_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, relative_path)


def format_seconds(seconds):
    try:
        seconds = float(seconds)
    except Exception:
        return "00:00:00"
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def find_ffmpeg():
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe

    local_appdata = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        os.path.join(local_appdata, "Microsoft", "WinGet", "Links", "ffmpeg.exe"),
        os.path.join(local_appdata, "Microsoft", "WinGet", "Links", "ffprobe.exe"),
    ]

    ffmpeg_candidate = candidates[0] if os.path.exists(candidates[0]) else None
    ffprobe_candidate = candidates[1] if os.path.exists(candidates[1]) else None

    if ffmpeg_candidate and ffprobe_candidate:
        return ffmpeg_candidate, ffprobe_candidate

    return None, None


def probe_duration(ffprobe_path, input_path):
    cmd = [
        ffprobe_path,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        input_path
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        return duration
    except Exception:
        return None


class ConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(APP_GEOMETRY)
        self.root.minsize(920, 620)
        self.root.configure(bg=BG)

        self.ffmpeg_path, self.ffprobe_path = find_ffmpeg()
        self.jobs = []
        self.log_queue = queue.Queue()
        self.convert_thread = None
        self.cancel_requested = False
        self.active_process = None

        self.output_format_var = tk.StringVar(value="mp3")
        self.bitrate_var = tk.StringVar(value="320k")
        self.sample_rate_var = tk.StringVar(value="44100")
        self.output_mode_var = tk.StringVar(value="folder")
        self.output_dir_var = tk.StringVar(value=os.path.join(os.getcwd(), "converted"))
        self.open_folder_after_var = tk.BooleanVar(value=True)
        self.skip_existing_var = tk.BooleanVar(value=True)

        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.file_progress_var = tk.DoubleVar(value=0.0)
        self.current_file_var = tk.StringVar(value="No active conversion")
        self.summary_var = tk.StringVar(value="0 file(s) queued")

        self._build_style()
        self._build_ui()
        self._refresh_ffmpeg_status()
        self._poll_log_queue()

    def _build_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD, relief="flat")
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 20, "bold"))
        style.configure("Sub.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background=CARD, foreground=TEXT, font=("Segoe UI", 11, "bold"))
        style.configure("CardText.TLabel", background=CARD, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("MutedCard.TLabel", background=CARD, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("TButton", font=("Segoe UI", 10), padding=10)
        style.map("TButton", background=[("active", ACCENT_2)])
        style.configure("Accent.TButton", background=ACCENT, foreground="white", borderwidth=0)
        style.map("Accent.TButton", background=[("active", ACCENT_2)])
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("Horizontal.TProgressbar", thickness=14)

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 12))

        ttk.Label(header, text="Home Media Converter", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Offline converter for common audio/video files using FFmpeg",
            style="Sub.TLabel"
        ).pack(anchor="w", pady=(4, 0))

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)

        right = ttk.Frame(body, width=290)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)

        self._build_queue_card(left)
        self._build_progress_card(left)
        self._build_settings_card(right)
        self._build_actions_card(right)
        self._build_log_card(right)

    def _build_queue_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="both", expand=True)

        top = ttk.Frame(card)
        top.pack(fill="x")

        ttk.Label(top, text="Queue", style="CardTitle.TLabel").pack(side="left")
        ttk.Label(top, textvariable=self.summary_var, style="MutedCard.TLabel").pack(side="right")

        btns = ttk.Frame(card)
        btns.pack(fill="x", pady=(10, 12))

        ttk.Button(btns, text="Add Files", command=self.add_files).pack(side="left")
        ttk.Button(btns, text="Add Folder", command=self.add_folder).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Remove Selected", command=self.remove_selected).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Clear Queue", command=self.clear_queue).pack(side="left", padx=(8, 0))

        columns = ("name", "type", "duration", "status", "output")
        self.tree = ttk.Treeview(card, columns=columns, show="headings", selectmode="extended")
        self.tree.pack(fill="both", expand=True)

        self.tree.heading("name", text="Source File")
        self.tree.heading("type", text="Type")
        self.tree.heading("duration", text="Duration")
        self.tree.heading("status", text="Status")
        self.tree.heading("output", text="Target")

        self.tree.column("name", width=360, anchor="w")
        self.tree.column("type", width=70, anchor="center")
        self.tree.column("duration", width=90, anchor="center")
        self.tree.column("status", width=110, anchor="center")
        self.tree.column("output", width=110, anchor="center")

        yscroll = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=yscroll.set)
        yscroll.place(relx=1.0, rely=0.12, relheight=0.86, anchor="ne")

    def _build_progress_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="x", pady=(12, 0))

        ttk.Label(card, text="Progress", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, textvariable=self.current_file_var, style="CardText.TLabel").pack(anchor="w", pady=(8, 4))

        ttk.Progressbar(card, variable=self.file_progress_var, maximum=100).pack(fill="x")
        self.file_progress_label = ttk.Label(card, text="Current file: 0%", style="MutedCard.TLabel")
        self.file_progress_label.pack(anchor="w", pady=(6, 8))

        ttk.Progressbar(card, variable=self.progress_var, maximum=100).pack(fill="x")
        self.total_progress_label = ttk.Label(card, text="Queue: 0%", style="MutedCard.TLabel")
        self.total_progress_label.pack(anchor="w", pady=(6, 0))

    def _build_settings_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="x")

        ttk.Label(card, text="Settings", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))

        row1 = ttk.Frame(card)
        row1.pack(fill="x", pady=(0, 8))
        ttk.Label(row1, text="Output format", style="CardText.TLabel").pack(anchor="w")
        ttk.Combobox(
            row1,
            textvariable=self.output_format_var,
            values=OUTPUT_FORMATS,
            state="readonly"
        ).pack(fill="x", pady=(4, 0))

        row2 = ttk.Frame(card)
        row2.pack(fill="x", pady=(0, 8))
        ttk.Label(row2, text="Audio bitrate", style="CardText.TLabel").pack(anchor="w")
        ttk.Combobox(
            row2,
            textvariable=self.bitrate_var,
            values=BITRATES,
            state="readonly"
        ).pack(fill="x", pady=(4, 0))

        row3 = ttk.Frame(card)
        row3.pack(fill="x", pady=(0, 8))
        ttk.Label(row3, text="Sample rate", style="CardText.TLabel").pack(anchor="w")
        ttk.Combobox(
            row3,
            textvariable=self.sample_rate_var,
            values=["22050", "32000", "44100", "48000"],
            state="readonly"
        ).pack(fill="x", pady=(4, 0))

        row4 = ttk.Frame(card)
        row4.pack(fill="x", pady=(0, 8))
        ttk.Label(row4, text="Output location", style="CardText.TLabel").pack(anchor="w", pady=(0, 4))
        modes = ttk.Frame(row4)
        modes.pack(fill="x")
        ttk.Radiobutton(
            modes, text="Same folder", value="same", variable=self.output_mode_var, command=self._toggle_output_dir
        ).pack(side="left")
        ttk.Radiobutton(
            modes, text="Custom folder", value="folder", variable=self.output_mode_var, command=self._toggle_output_dir
        ).pack(side="left", padx=(10, 0))

        outdir = ttk.Frame(card)
        outdir.pack(fill="x", pady=(0, 8))
        self.output_entry = ttk.Entry(outdir, textvariable=self.output_dir_var)
        self.output_entry.pack(side="left", fill="x", expand=True)
        self.output_browse_btn = ttk.Button(outdir, text="Browse", command=self.choose_output_dir)
        self.output_browse_btn.pack(side="left", padx=(8, 0))

        ttk.Checkbutton(card, text="Skip if target already exists", variable=self.skip_existing_var).pack(anchor="w")
        ttk.Checkbutton(card, text="Open output folder when finished", variable=self.open_folder_after_var).pack(anchor="w", pady=(4, 0))

        self._toggle_output_dir()

    def _build_actions_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="x", pady=(12, 0))

        ttk.Label(card, text="Actions", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))

        ttk.Button(card, text="Start Conversion", style="Accent.TButton", command=self.start_conversion).pack(fill="x")
        ttk.Button(card, text="Cancel Current Job", command=self.cancel_conversion).pack(fill="x", pady=(8, 0))
        ttk.Button(card, text="Open Output Folder", command=self.open_output_folder).pack(fill="x", pady=(8, 0))

        ttk.Separator(card, orient="horizontal").pack(fill="x", pady=12)

        self.ffmpeg_status_label = ttk.Label(card, text="", style="MutedCard.TLabel")
        self.ffmpeg_status_label.pack(anchor="w")
        self.status_label = ttk.Label(card, textvariable=self.status_var, style="MutedCard.TLabel")
        self.status_label.pack(anchor="w", pady=(8, 0))

    def _build_log_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="both", expand=True, pady=(12, 0))

        ttk.Label(card, text="Log", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))

        self.log_text = tk.Text(
            card,
            height=10,
            wrap="word",
            bg="#f8fafc",
            fg=TEXT,
            relief="flat",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=BORDER,
            font=("Consolas", 9)
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

    def _toggle_output_dir(self):
        state = "normal" if self.output_mode_var.get() == "folder" else "disabled"
        self.output_entry.configure(state=state)
        self.output_browse_btn.configure(state=state)

    def _refresh_ffmpeg_status(self):
        if self.ffmpeg_path and self.ffprobe_path:
            self.ffmpeg_status_label.configure(text=f"FFmpeg detected: {self.ffmpeg_path}")
        else:
            self.ffmpeg_status_label.configure(
                text="FFmpeg / FFprobe not found. Install with: winget install ffmpeg"
            )

    def log(self, message):
        self.log_queue.put(("log", message))

    def _poll_log_queue(self):
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "log":
                    self.log_text.configure(state="normal")
                    self.log_text.insert("end", payload + "\n")
                    self.log_text.see("end")
                    self.log_text.configure(state="disabled")
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "current":
                    self.current_file_var.set(payload)
                elif kind == "file_progress":
                    self.file_progress_var.set(payload)
                    self.file_progress_label.configure(text=f"Current file: {payload:.1f}%")
                elif kind == "total_progress":
                    self.progress_var.set(payload)
                    self.total_progress_label.configure(text=f"Queue: {payload:.1f}%")
                elif kind == "tree_status":
                    item_id, status_text = payload
                    values = list(self.tree.item(item_id, "values"))
                    if values:
                        values[3] = status_text
                        self.tree.item(item_id, values=values)
                elif kind == "summary":
                    self.summary_var.set(payload)
        except queue.Empty:
            pass
        self.root.after(120, self._poll_log_queue)

    def _update_summary(self):
        self.summary_var.set(f"{len(self.jobs)} file(s) queued")

    def _iter_supported_files(self, paths):
        for path in paths:
            if os.path.isfile(path) and os.path.splitext(path)[1].lower() in INPUT_EXTENSIONS:
                yield path

    def _output_path_for(self, input_path):
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        ext = self.output_format_var.get().lower()

        if self.output_mode_var.get() == "same":
            output_dir = os.path.dirname(input_path)
        else:
            output_dir = self.output_dir_var.get().strip() or os.path.join(os.getcwd(), "converted")

        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, f"{base_name}.{ext}")

    def add_files(self):
        filetypes = [("Media files", " ".join(f"*{ext}" for ext in sorted(INPUT_EXTENSIONS))), ("All files", "*.*")]
        paths = filedialog.askopenfilenames(title="Select files", filetypes=filetypes)
        if not paths:
            return
        self._add_job_paths(paths)

    def add_folder(self):
        folder = filedialog.askdirectory(title="Select folder")
        if not folder:
            return

        found = []
        for root, _, files in os.walk(folder):
            for name in files:
                full = os.path.join(root, name)
                if os.path.splitext(name)[1].lower() in INPUT_EXTENSIONS:
                    found.append(full)

        if not found:
            messagebox.showinfo(APP_TITLE, "No supported media files were found in that folder.")
            return

        self._add_job_paths(found)

    def _add_job_paths(self, paths):
        existing = {job["input_path"] for job in self.jobs}
        added = 0

        for path in paths:
            if path in existing:
                continue
            if os.path.splitext(path)[1].lower() not in INPUT_EXTENSIONS:
                continue

            duration = probe_duration(self.ffprobe_path, path) if self.ffprobe_path else None
            item_id = self.tree.insert(
                "",
                "end",
                values=(
                    os.path.basename(path),
                    os.path.splitext(path)[1].lower().replace(".", "").upper(),
                    format_seconds(duration) if duration else "Unknown",
                    "Queued",
                    self.output_format_var.get().upper()
                )
            )
            self.jobs.append({
                "item_id": item_id,
                "input_path": path,
                "duration": duration,
                "status": "Queued"
            })
            added += 1

        self._update_summary()
        self.log(f"Added {added} file(s) to queue.")

    def remove_selected(self):
        selected = set(self.tree.selection())
        if not selected:
            return
        self.jobs = [job for job in self.jobs if job["item_id"] not in selected]
        for item_id in selected:
            self.tree.delete(item_id)
        self._update_summary()
        self.log(f"Removed {len(selected)} selected file(s).")

    def clear_queue(self):
        if self.convert_thread and self.convert_thread.is_alive():
            messagebox.showwarning(APP_TITLE, "Cannot clear the queue while conversion is running.")
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.jobs.clear()
        self._update_summary()
        self.progress_var.set(0)
        self.file_progress_var.set(0)
        self.current_file_var.set("No active conversion")
        self.log("Queue cleared.")

    def choose_output_dir(self):
        folder = filedialog.askdirectory(title="Choose output folder")
        if folder:
            self.output_dir_var.set(folder)

    def open_output_folder(self):
        if self.output_mode_var.get() == "same":
            if self.jobs:
                folder = os.path.dirname(self.jobs[0]["input_path"])
            else:
                folder = os.getcwd()
        else:
            folder = self.output_dir_var.get().strip() or os.path.join(os.getcwd(), "converted")
            os.makedirs(folder, exist_ok=True)

        try:
            os.startfile(folder)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not open folder:\n{e}")

    def _build_ffmpeg_command(self, input_path, output_path):
        fmt = self.output_format_var.get().lower()
        bitrate = self.bitrate_var.get()
        sample_rate = self.sample_rate_var.get()

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", input_path,
            *FORMAT_CODEC_ARGS[fmt],
        ]

        if fmt in {"mp3", "aac", "m4a", "ogg"}:
            cmd += ["-b:a", bitrate]

        if fmt != "flac":
            cmd += ["-ar", sample_rate]

        if fmt == "m4a":
            cmd += ["-f", "ipod"]
        elif fmt == "ogg":
            cmd += ["-f", "ogg"]

        cmd += [
            "-progress", "pipe:1",
            "-nostats",
            output_path
        ]
        return cmd

    def start_conversion(self):
        if not self.ffmpeg_path or not self.ffprobe_path:
            messagebox.showerror(
                APP_TITLE,
                "FFmpeg / FFprobe not found.\n\nInstall first with:\nwinget install ffmpeg"
            )
            return

        if not self.jobs:
            messagebox.showinfo(APP_TITLE, "No files in queue.")
            return

        if self.convert_thread and self.convert_thread.is_alive():
            messagebox.showinfo(APP_TITLE, "Conversion is already running.")
            return

        if self.output_mode_var.get() == "folder":
            output_dir = self.output_dir_var.get().strip()
            if not output_dir:
                messagebox.showwarning(APP_TITLE, "Please choose an output folder.")
                return
            os.makedirs(output_dir, exist_ok=True)

        self.cancel_requested = False
        self.convert_thread = threading.Thread(target=self._convert_worker, daemon=True)
        self.convert_thread.start()

    def cancel_conversion(self):
        self.cancel_requested = True
        if self.active_process and self.active_process.poll() is None:
            try:
                self.active_process.terminate()
                self.log("Cancellation requested.")
            except Exception:
                pass

    def _convert_worker(self):
        total_jobs = len(self.jobs)
        completed = 0
        self.log_queue.put(("status", "Running"))

        for index, job in enumerate(self.jobs, start=1):
            item_id = job["item_id"]
            input_path = job["input_path"]
            output_path = self._output_path_for(input_path)
            duration = job["duration"]

            if self.cancel_requested:
                self.log_queue.put(("tree_status", (item_id, "Cancelled")))
                continue

            if self.skip_existing_var.get() and os.path.exists(output_path):
                self.log_queue.put(("tree_status", (item_id, "Skipped")))
                self.log(f"Skipped existing file: {os.path.basename(output_path)}")
                completed += 1
                self.log_queue.put(("total_progress", completed / total_jobs * 100))
                continue

            self.log_queue.put(("tree_status", (item_id, "Converting")))
            self.log_queue.put(("current", f"Converting {os.path.basename(input_path)}"))
            self.log_queue.put(("file_progress", 0.0))

            cmd = self._build_ffmpeg_command(input_path, output_path)
            self.log(f"Starting: {os.path.basename(input_path)} -> {os.path.basename(output_path)}")

            try:
                self.active_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    universal_newlines=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                )

                last_pct = 0.0
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
                            seconds_done = out_ms / 1_000_000.0
                            pct = min(100.0, (seconds_done / duration) * 100.0)
                            if pct >= last_pct:
                                last_pct = pct
                                self.log_queue.put(("file_progress", pct))
                                queue_pct = ((completed + pct / 100.0) / total_jobs) * 100.0
                                self.log_queue.put(("total_progress", queue_pct))
                        except Exception:
                            pass
                    elif line.startswith("progress="):
                        if line.endswith("end"):
                            self.log_queue.put(("file_progress", 100.0))
                return_code = self.active_process.wait()
                self.active_process = None

                if self.cancel_requested:
                    self.log_queue.put(("tree_status", (item_id, "Cancelled")))
                    self.log(f"Cancelled: {os.path.basename(input_path)}")
                elif return_code == 0:
                    self.log_queue.put(("tree_status", (item_id, "Done")))
                    self.log(f"Done: {os.path.basename(output_path)}")
                else:
                    self.log_queue.put(("tree_status", (item_id, "Failed")))
                    self.log(f"Failed: {os.path.basename(input_path)}")

            except Exception as e:
                self.active_process = None
                self.log_queue.put(("tree_status", (item_id, "Failed")))
                self.log(f"Error on {os.path.basename(input_path)}: {e}")

            completed += 1
            self.log_queue.put(("total_progress", completed / total_jobs * 100))

        self.log_queue.put(("current", "No active conversion"))
        self.log_queue.put(("status", "Finished" if not self.cancel_requested else "Stopped"))

        if self.open_folder_after_var.get() and not self.cancel_requested:
            try:
                if self.output_mode_var.get() == "folder":
                    folder = self.output_dir_var.get().strip()
                else:
                    folder = os.path.dirname(self.jobs[0]["input_path"]) if self.jobs else os.getcwd()
                os.startfile(folder)
            except Exception:
                pass

    def run(self):
        self.root.mainloop()


def main():
    root = tk.Tk()
    app = ConverterApp(root)
    app.run()


if __name__ == "__main__":
    main()
