"""
Stage 2 — Content Processing.
Text is handled with plain cleanup. Audio is transcribed with Groq's hosted
Whisper when GROQ_API_KEY is set, otherwise (or if that call fails) with local
faster-whisper. Video is handled as keyframe OCR (on-screen text overlays,
common in WhatsApp-forward reels) fused with a transcript of its audio track.
"""
import os
import re
import subprocess
import tempfile
import unicodedata

import cv2
import httpx
from faster_whisper import WhisperModel

from config import DEVICE, GROQ_API_KEY, GROQ_WHISPER_MODEL, LOCAL_WHISPER_MODEL
from progress import step, done

_GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
_GROQ_MAX_BYTES = 25 * 1024 * 1024  # Groq free-tier upload limit
# Biases Whisper toward spelling medical vocabulary correctly.
_GROQ_PROMPT = "A social media video making health and medical claims about diseases, drugs, vaccines and remedies."

# ctranslate2 (faster-whisper's backend) has no MPS kernel yet, so fall back to CPU there.
_WHISPER_DEVICE = "cpu" if DEVICE == "mps" else DEVICE
_WHISPER_COMPUTE_TYPE = "int8" if _WHISPER_DEVICE == "cpu" else "float16"

_whisper_model = None
_ocr_reader = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        step(f"Loading Whisper model '{LOCAL_WHISPER_MODEL}' (device={_WHISPER_DEVICE}, first time only)...")
        _whisper_model = WhisperModel(
            LOCAL_WHISPER_MODEL, device=_WHISPER_DEVICE, compute_type=_WHISPER_COMPUTE_TYPE
        )
        done("Whisper model loaded.")
    return _whisper_model


def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        step("Loading EasyOCR reader (downloads OCR weights on first run)...")
        import easyocr  # heavy import (pulls in torch init) — deferred until first use

        _ocr_reader = easyocr.Reader(["en"], gpu=False)
        done("EasyOCR reader loaded.")
    return _ocr_reader


def clean_text(raw: str) -> str:
    """Normalize WhatsApp-forward style text: strip forwarded headers,
    excess emoji/whitespace, fix broken unicode from copy-paste chains."""
    text = unicodedata.normalize("NFKC", raw)
    text = re.sub(r"\[?\s*Forwarded\s*\]?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"http\S+", "", text)                     # strip bare URLs (kept separately if needed)
    text = re.sub(r"[\U0001F300-\U0001FAFF]", "", text)      # strip emoji block
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_audio(path: str) -> str:
    """Strip the audio track out of `path` as 16 kHz mono 32 kbps mp3 — about
    14 MB per hour, so even long videos fit under Groq's upload limit."""
    fd, out_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", path,
         "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", out_path],
        check=True,
    )
    return out_path


def _transcribe_groq(path: str) -> str:
    step(f"Transcribing audio (Groq {GROQ_WHISPER_MODEL})...")
    audio_path = _extract_audio(path)
    try:
        if os.path.getsize(audio_path) > _GROQ_MAX_BYTES:
            raise ValueError("audio exceeds Groq's 25 MB upload limit")
        with open(audio_path, "rb") as f:
            resp = httpx.post(
                _GROQ_TRANSCRIBE_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": ("audio.mp3", f, "audio/mpeg")},
                data={"model": GROQ_WHISPER_MODEL, "prompt": _GROQ_PROMPT, "temperature": "0"},
                timeout=300,
            )
        resp.raise_for_status()
        return resp.json()["text"].strip()
    finally:
        os.remove(audio_path)


def _transcribe_local(path: str) -> str:
    step(f"Transcribing audio (local faster-whisper '{LOCAL_WHISPER_MODEL}')...")
    segments, _ = _get_whisper().transcribe(path, beam_size=5)
    return " ".join(seg.text.strip() for seg in segments)


def transcribe_audio(path: str) -> str:
    """Transcribe the audio track at `path` (any ffmpeg-readable file, including
    a video's soundtrack). Uses Groq when GROQ_API_KEY is set, and falls back
    to local faster-whisper if there's no key or the Groq call fails."""
    text = None
    if GROQ_API_KEY:
        try:
            text = _transcribe_groq(path)
        except Exception as e:
            step(f"Groq transcription failed ({e}) — falling back to local faster-whisper.")
    if text is None:
        text = _transcribe_local(path)
    done(f"Audio transcription complete ({len(text)} chars).")
    return text


def extract_video_frames_and_text(path: str, frame_interval_sec: float = 2.0) -> str:
    """Sample keyframes with OpenCV, OCR on-screen text overlays with EasyOCR,
    and fuse that with a transcript of the video's audio track."""
    reader = _get_ocr_reader()
    step("Scanning video keyframes for on-screen text (OCR)...")
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    frame_step = max(int(fps * frame_interval_sec), 1)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    seen = set()
    overlay_texts = []
    frame_idx = 0
    frames_scanned = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % frame_step == 0:
            frames_scanned += 1
            for text in reader.readtext(frame, detail=0):
                normalized = text.strip()
                if normalized and normalized.lower() not in seen:
                    seen.add(normalized.lower())
                    overlay_texts.append(normalized)
            if total_frames:
                pct = min(100, round(100 * frame_idx / total_frames))
                step(f"  OCR keyframe {frames_scanned} (~{pct}% through video)...")
        frame_idx += 1
    cap.release()
    done(f"OCR scan complete — {frames_scanned} keyframes checked, {len(overlay_texts)} text snippets found.")

    overlay_text = " ".join(overlay_texts)
    audio_text = transcribe_audio(path)
    return " ".join(part for part in (overlay_text, audio_text) if part)


def unify_to_text(user_input: str, input_type: str = "text") -> str:
    """Stage-2 output: 'Unified Textual Representation' in the diagram."""
    step(f"Stage 2: unifying input (type={input_type}) to text...")
    if input_type == "text":
        result = clean_text(user_input)
    elif input_type == "audio":
        result = clean_text(transcribe_audio(user_input))
    elif input_type == "video":
        result = clean_text(extract_video_frames_and_text(user_input))
    else:
        raise ValueError(f"Unknown input_type: {input_type}")
    done("Stage 2 complete.")
    return result
