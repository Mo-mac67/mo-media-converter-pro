MO MEDIA CONVERTER PRO v3

WHAT'S NEW
- Direct URL downloader tab
- Legal-use disclaimer inside the app
- Download history
- Auto-add downloaded file to converter queue

IMPORTANT
This downloader is for direct, public, authorized file URLs only.
Do not use it to infringe copyright, bypass platform restrictions,
or download media you do not have the right to access.

SUPPORTED DOWNLOADER USE
Good examples:
- Your own direct MP4/MP3/WAV/M4A files
- Public asset links from your own site or CDN
- Direct podcast/media file URLs
- Other openly downloadable files

NOT INCLUDED
This is not a site-ripping downloader for platforms or social networks.

INSTALLATION
1) Check Python:
   python --version

2) Install FFmpeg:
   winget install ffmpeg

3) Optional drag & drop:
   python -m pip install tkinterdnd2

RUN
python mo_media_converter_pro_v3.py

BUILD EXE
python -m pip install pyinstaller
pyinstaller --noconsole --onefile mo_media_converter_pro_v3.py

OPTIONAL ICON
pyinstaller --noconsole --onefile --icon youricon.ico mo_media_converter_pro_v3.py

APP DATA
Settings, presets, and history are stored in:
%USERPROFILE%\.mo_media_converter_pro
