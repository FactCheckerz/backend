from pathlib import Path
from groq import Groq
from app.core.config import GROQ_API_KEY,WHISPER_MODEL
from app.services.ingestion.exceptions import IngestionError
from app.services.ingestion.exceptions import TranscriptionError

def transcribe_audio(audio_path: str) -> str:
    """
    Send a local audio/media file to Groq Whisper and return Normalized text
    """
    if not GROQ_API_KEY:
        raise TranscriptionError("GROQ_API_KEY is not configured. Audio transcription cannot run")

    path = Path(audio_path)
    if not path.exists():
        raise TranscriptionError("Audio file for transcription does not exist")

    try:
        client = Groq(api_key=GROQ_API_KEY)
        with path.open("rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=audio_file,
                model=WHISPER_MODEL,
                response_format="json",
                temperature=0.0
            )
        text = (transcription.text or "").strip()
        if not text:
            raise TranscriptionError("No speech was detected in supplied media")
        return " ".join(text.split())
    except TranscriptionError:
        raise
    except Exception as exc:
        raise TranscriptionError("Speech to text transcription failed") from exc