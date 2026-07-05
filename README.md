# 🎛️ Mo Media Converter Pro

A free, open-source desktop app (Windows, Python + FFmpeg) for everyday media
tasks: convert audio/video, download direct file URLs, and now **generate and
translate subtitles**.

> Latest version: **v6** — `mo_media_converter_pro_v6.py`

---

## ✨ Features

**Converter**
- Convert between audio (mp3, wav, flac, aac, m4a, ogg, opus) and video
  (mp4, mkv, mov, webm) formats
- Batch queue, presets, drag & drop, progress + ETA

**Downloader**
- Download direct, public, authorized file URLs; optional auto-add to the queue

**Subtitles (new in v6)**
- Give it a video/audio file → extracts the audio, transcribes speech
  **offline** with Whisper, and saves an `.srt`
- Optional **free translation** to 30+ languages (Google, via deep-translator)
- Translate an existing `.srt` directly
- Optional soft-sub embedding into a copy of the video (no re-encode)
- Protects formatting tags (`<i>`, `{\an8}`) and adds a "machine-generated"
  notice so viewers know it's automatic

---

## 🚀 Setup

```bash
# 1) FFmpeg
winget install ffmpeg

# 2) Subtitle features (optional)
python -m pip install faster-whisper deep-translator

# 3) Drag & drop (optional)
python -m pip install tkinterdnd2

# Run
python mo_media_converter_pro_v6.py
```

Build a standalone exe:

```bash
python -m pip install pyinstaller
pyinstaller --noconsole --onefile mo_media_converter_pro_v6.py
```

---

## 📝 Notes

- Transcription is fully offline; only translation needs internet.
- Machine translation is a **draft** — for the highest quality on idioms and
  tone, a human pass or an LLM engine is recommended.
- Use the downloader only for content you have the right to access.

## 📄 License

MIT — free to use, modify, and **fork**. See [LICENSE](LICENSE).
