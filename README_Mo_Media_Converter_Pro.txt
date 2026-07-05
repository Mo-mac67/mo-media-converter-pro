Mo Media Converter Pro

What it does
- Offline desktop media converter
- Batch queue
- Audio output: MP3, WAV, FLAC, AAC, M4A, OGG, OPUS
- Video output: MP4, MKV, MOV, WEBM
- Presets: Music, Voice, YouTube Audio, YouTube Video, Archive Lossless, Mobile Small
- Progress bars
- Optional drag & drop
- Dark Windows-style UI

Requirements
1) Install FFmpeg:
   winget install ffmpeg

2) Optional drag & drop support:
   pip install tkinterdnd2

Run
python mo_media_converter_pro.py

Optional EXE build
pip install pyinstaller
pyinstaller --noconsole --onefile mo_media_converter_pro.py
