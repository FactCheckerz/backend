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

# ctranslate2 (faster-whisper's backend) has no MPS kernel yet, so fall back to CPU there.
_WHISPER_DEVICE = "cpu" if DEVICE == "mps" else DEVICE
_WHISPER_COMPUTE_TYPE = "int8" if _WHISPER_DEVICE == "cpu" else "float16"

_whisper_model = None
_ocr_reader = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel(
            "base", device=_WHISPER_DEVICE, compute_type=_WHISPER_COMPUTE_TYPE
        )
    return _whisper_model


def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr  # heavy import (pulls in torch init) — deferred until first use

        _ocr_reader = easyocr.Reader(["en"], gpu=False)
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
    segments, _ = _get_whisper().transcribe(path, beam_size=5)
    return " ".join(seg.text.strip() for seg in segments)


def extract_video_frames_and_text(path: str, frame_interval_sec: float = 2.0) -> str:
    """Sample keyframes with OpenCV, OCR on-screen text overlays with EasyOCR,
    and fuse that with a transcript of the video's audio track."""
    reader = _get_ocr_reader()
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    frame_step = max(int(fps * frame_interval_sec), 1)

    seen = set()
    overlay_texts = []
    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % frame_step == 0:
            for text in reader.readtext(frame, detail=0):
                normalized = text.strip()
                if normalized and normalized.lower() not in seen:
                    seen.add(normalized.lower())
                    overlay_texts.append(normalized)
        frame_idx += 1
    cap.release()

    overlay_text = " ".join(overlay_texts)
    audio_text = transcribe_audio(path)
    return " ".join(part for part in (overlay_text, audio_text) if part)


def unify_to_text(user_input: str, input_type: str = "text") -> str:
    """Stage-2 output: 'Unified Textual Representation' in the diagram."""
    if input_type == "text":
        return clean_text(user_input)
    elif input_type == "audio":
        return clean_text(transcribe_audio(user_input))
    elif input_type == "video":
        return clean_text(extract_video_frames_and_text(user_input))
    raise ValueError(f"Unknown input_type: {input_type}")
