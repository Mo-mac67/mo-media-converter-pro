MO MEDIA CONVERTER PRO v6

WHAT'S NEW IN v6
- New "Subtitles" tab:
  * Give it a video (or audio) file -> it extracts the audio with FFmpeg,
    transcribes the speech OFFLINE with Whisper, and saves an .srt subtitle
    next to the source file.
  * Optional free translation of the subtitles to 30+ languages
    (Google, via deep-translator, needs internet).
  * Translate any existing .srt file directly (no video needed).
  * Optional: embed the subtitle into a copy of the video as a soft-sub
    (stream copy, no re-encode, instant).

INSTALLATION
1) Check Python:
   python --version

2) Install FFmpeg:
   winget install ffmpeg

3) Subtitle features:
   python -m pip install faster-whisper deep-translator

4) Optional drag & drop:
   python -m pip install tkinterdnd2

RUN
python mo_media_converter_pro_v6.py

SUBTITLES - HOW TO USE
1) Open the "Subtitles" tab.
2) Choose your video/audio file.
3) Pick a Whisper model:
   - tiny/base : fastest, okay quality
   - small     : good balance (recommended)
   - medium/large-v3 : best quality, slow on CPU
4) Leave "Spoken language" on Auto Detect (or set it).
5) Pick "Translate subtitles to" (or keep original language).
6) Click "Generate Subtitles".
   Output: movie.fa.srt (etc.) next to the video.
   First run of each model downloads it once (~75 MB base, ~500 MB small).

NOTES
- Transcription is fully offline; only translation needs internet.
- Soft-sub embedding produces movie.subbed.mkv / movie.subbed.mp4
  without re-encoding (fast, lossless).

BUILD EXE
python -m pip install pyinstaller
pyinstaller --noconsole --onefile mo_media_converter_pro_v6.py

APP DATA
Settings, presets, and history are stored in:
%USERPROFILE%\.mo_media_converter_pro
Whisper models are cached in:
%USERPROFILE%\.cache\huggingface
