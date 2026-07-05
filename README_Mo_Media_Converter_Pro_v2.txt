MO MEDIA CONVERTER PRO v2

FILES
- mo_media_converter_pro_v2.py
- README_Mo_Media_Converter_Pro_v2.txt

NEW IN v2
- Saves last-used settings automatically
- Save and delete your own custom presets
- ETA estimate during conversion
- Open app data folder from the UI
- Updated setup guide
- Better polished dark Windows-style layout

SUPPORTED INPUT
Video:
MP4, MKV, AVI, MOV, WMV, WEBM, M4V, FLV, MPEG, MPG, TS, MTS

Audio:
MP3, WAV, FLAC, AAC, M4A, OGG, OPUS, WMA, AIFF, AIF, AMR

SUPPORTED OUTPUT
Audio:
MP3, WAV, FLAC, AAC, M4A, OGG, OPUS

Video:
MP4, MKV, MOV, WEBM

INSTALLATION
1) Make sure Python works:
   python --version

2) Install FFmpeg:
   winget install ffmpeg

3) Optional drag & drop support:
   python -m pip install tkinterdnd2

RUN
python mo_media_converter_pro_v2.py

EXE BUILD
1) Install PyInstaller:
   python -m pip install pyinstaller

2) Build EXE:
   pyinstaller --noconsole --onefile mo_media_converter_pro_v2.py

3) Build EXE with icon:
   pyinstaller --noconsole --onefile --icon youricon.ico mo_media_converter_pro_v2.py

WHERE SETTINGS ARE SAVED
The program stores settings and custom presets in:
%USERPROFILE%\.mo_media_converter_pro

FILES INSIDE THAT FOLDER
- settings.json
- custom_presets.json

NOTES
- If tkinterdnd2 is not installed, the app still works. Only drag & drop is disabled.
- ETA is an estimate, not an exact promise.
- WEBM output is kept on a compatibility-focused codec path automatically.

USAGE
1) Add files or a whole folder
2) Choose preset or custom settings
3) Choose output type and format
4) Start conversion
5) Save your favorite settings as a custom preset if needed
