"""
Stage 2 — Content Processing.
Text is handled with plain cleanup. Audio is transcribed with faster-whisper.
Video is handled as keyframe OCR (on-screen text overlays, common in
WhatsApp-forward reels) fused with a transcript of its audio track.
"""
import re
import unicodedata

import cv2
from faster_whisper import WhisperModel

from config import DEVICE
from progress import step, done

# ctranslate2 (faster-whisper's backend) has no MPS kernel yet, so fall back to CPU there.
_WHISPER_DEVICE = "cpu" if DEVICE == "mps" else DEVICE
_WHISPER_COMPUTE_TYPE = "int8" if _WHISPER_DEVICE == "cpu" else "float16"

_whisper_model = None
_ocr_reader = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        step(f"Loading Whisper model (device={_WHISPER_DEVICE}, first time only)...")
        _whisper_model = WhisperModel(
            "base", device=_WHISPER_DEVICE, compute_type=_WHISPER_COMPUTE_TYPE
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


def transcribe_audio(path: str) -> str:
    """Transcribe the audio track at `path` (any ffmpeg-readable file, including
    a video's soundtrack) with faster-whisper."""
    step("Transcribing audio (faster-whisper)...")
    segments, _ = _get_whisper().transcribe(path, beam_size=5)
    text = " ".join(seg.text.strip() for seg in segments)
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
