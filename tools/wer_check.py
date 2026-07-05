"""Measure Whisper transcription accuracy (WER) against a reference subtitle.

Usage:
    python tools/wer_check.py --media episode.mkv --ref english.srt
    python tools/wer_check.py --media clip.wav --ref transcript.srt --model small --lang en

IMPORTANT: the reference must be a *transcript in the same language that is
spoken* (e.g. an English .srt for English audio). A translated subtitle
(e.g. Persian) cannot be used to measure word error rate.

Requires: faster-whisper, jiwer, and FFmpeg on PATH.
    python -m pip install faster-whisper jiwer
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time


def read_text_any_encoding(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()
    for enc in ("utf-8-sig", "utf-8", "cp1256", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def srt_to_text(path: str) -> str:
    """Extract just the spoken words from a .srt (drop indices/timestamps/tags)."""
    raw = read_text_any_encoding(path)
    lines = []
    for line in raw.replace("\r\n", "\n").split("\n"):
        s = line.strip()
        if not s or s.isdigit() or "-->" in s:
            continue
        lines.append(s)
    return " ".join(lines)


def normalize(text: str) -> str:
    """Lowercase, strip markup/punctuation, collapse whitespace for fair WER."""
    text = text.lower()
    text = re.sub(r"<[^>]+>", " ", text)          # HTML-like tags
    text = re.sub(r"\{[^}]*\}", " ", text)        # ASS override blocks
    text = re.sub(r"[^\w\s']", " ", text, flags=re.UNICODE)  # punctuation
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_audio(media: str, ffmpeg: str) -> str:
    wav = os.path.join(tempfile.gettempdir(), f"wer_{os.getpid()}.wav")
    cmd = [ffmpeg, "-y", "-i", media, "-vn", "-ac", "1", "-ar", "16000",
           "-c:a", "pcm_s16le", wav]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(wav):
        raise SystemExit(f"FFmpeg failed to extract audio:\n{res.stderr[-500:]}")
    return wav


def main() -> None:
    ap = argparse.ArgumentParser(description="Whisper WER checker")
    ap.add_argument("--media", required=True, help="video or audio file")
    ap.add_argument("--ref", required=True, help="reference .srt (same language as speech)")
    ap.add_argument("--model", default="small", help="Whisper model (tiny/base/small/medium/large-v3)")
    ap.add_argument("--lang", default=None, help="force spoken language code (e.g. en); default auto")
    args = ap.parse_args()

    try:
        from faster_whisper import WhisperModel
        import jiwer
    except ImportError as e:
        raise SystemExit(f"Missing dependency: {e}\n  python -m pip install faster-whisper jiwer")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("FFmpeg not found on PATH. Install: winget install ffmpeg")

    is_audio = args.media.lower().endswith((".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg"))
    wav = args.media if is_audio else extract_audio(args.media, ffmpeg)

    print(f"Loading Whisper '{args.model}'...")
    model = WhisperModel(args.model, device="cpu", compute_type="int8")

    print("Transcribing...")
    t0 = time.time()
    segments, info = model.transcribe(wav, language=args.lang, vad_filter=True, beam_size=5)
    hyp = " ".join(seg.text for seg in segments)
    elapsed = time.time() - t0
    dur = info.duration or 0.0
    rtf = (dur / elapsed) if elapsed else 0.0

    if wav != args.media:
        try:
            os.remove(wav)
        except OSError:
            pass

    ref = srt_to_text(args.ref)
    ref_n, hyp_n = normalize(ref), normalize(hyp)

    out = jiwer.process_words(ref_n, hyp_n)
    ref_words = len(ref_n.split())

    print("\n===== RESULT =====")
    print(f"Detected language : {info.language} (p={info.language_probability:.2f})")
    print(f"Audio duration    : {dur:.0f}s   transcribe time: {elapsed:.0f}s   ({rtf:.1f}x realtime)")
    print(f"Reference words   : {ref_words}")
    print(f"WER               : {out.wer*100:.1f}%   (lower is better)")
    print(f"Word accuracy     : {(1-out.wer)*100:.1f}%")
    print(f"  substitutions   : {out.substitutions}")
    print(f"  deletions       : {out.deletions}   (missed words)")
    print(f"  insertions      : {out.insertions}   (hallucinated words)")
    if info.language != "en" and args.lang is None:
        print("\nNote: if the reference is a translation (different language than speech),"
              "\nthe WER above is meaningless. Use a same-language transcript.")


if __name__ == "__main__":
    main()
