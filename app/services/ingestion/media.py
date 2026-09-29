import shutil
import subprocess
import uuid
from pathlib import Path

from app.core.config import (
    MAX_AUDIO_DURATION_MINUTES,
    MAX_VIDEO_DURATION_MINUTES,
    MAX_AUDIO_SIZE_MB,
    MAX_VIDEO_SIZE_MB,
    TEMP_MEDIA_DIR
)

from app.services.ingestion.exceptions import (
    AudioExtractionError,
    InvalidInputError,
    MediaTooLargeError,
    MediaTooLongError
)

from app.services.ingestion.hashing import calculate_file_hash

ALLOWED_AUDIO_EXTENSIONS = {
    ".mp3",".wav",".m4a",".aac",".ogg",".flac"
}
ALLOWED_VIDEO_EXTENSIONS = {
    ".mp4",".mov",".mkv",".webm"
}


def ensure_temp_directory() -> Path:
    """Create and return temp media directory"""
    directory = Path(TEMP_MEDIA_DIR)
    directory.mkdir(
        parents=True,
        exist_ok=True
    )
    return directory

def validate_file_size(file_path:str,input_type:str) -> None:
    """Validates media file size"""
    file_size = Path(file_path).stat().st_size
    if input_type == "audio":
        max_size = MAX_AUDIO_SIZE_MB * 1024 *1024
    else:
        max_size = MAX_VIDEO_SIZE_MB * 1024 * 1024
    if file_size > max_size:
        raise MediaTooLargeError(
            f"{input_type} file exceeds the maximum"
            f"allowed size of"
            f"{max_size / (1024*1024):.0f} MB"
        )

def get_media_duration(file_path: str) -> float:
    """Get media duration using ffprobe"""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )
    if result.returncode!=0:
        raise InvalidInputError(
            "Unable to determine media duration"
        )
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise InvalidInputError(
            "Invalid Media Duration"
        )

def validate_media_duration(file_path: str, input_type: str) -> float:
    """Validate media duration and return it in seconds"""
    duration = get_media_duration(file_path)
    if input_type == "audio":
        max_duration = (
            MAX_AUDIO_DURATION_MINUTES * 60
        )
    else:
        max_duration = (
            MAX_VIDEO_DURATION_MINUTES * 60
        )
    if duration > max_duration:
        raise MediaTooLongError(
            f"{input_type} duration exceeds the maximum"
            f"allowed duration of"
            f"{max_duration / (1024*1024):.0f} minutes"
        )
    return duration

def save_uploaded_file(source_file,input_type:str,og_filename: str | None) -> Path:
    """Save an uploaded file temporarily"""
    temp_dir = ensure_temp_directory()
    extension = ""
    if og_filename:
        extension = Path(og_filename).suffix.lower()
    if input_type == "audio":
        if extension not in ALLOWED_AUDIO_EXTENSIONS:
            raise InvalidInputError(
                "Unsupported audio format"
            )
    else:
        if extension not in ALLOWED_VIDEO_EXTENSIONS:
            raise InvalidInputError(
                "Unsupported video format"
            )
    filename = (f"{uuid.uuid4().hex}"f"{extension}")
    destination = temp_dir / filename
    with destination.open("wb") as output:
        shutil.copyfileobj(
            source_file,
            output
        )
    return destination

def extract_audio(video_path: str) -> Path:
    """Extract audio using ffmpeg"""
    temp_dir = ensure_temp_directory()
    output_path = (
        temp_dir / f"{uuid.uuid4().hex}.wav"
    )
    command = [
        "ffmpeg",
        "-y",
        "i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "ar",
        "16000",
        "-c:a",
        "pcm_s161e",
        str(output_path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        if output_path.exists():
            output_path.unlink()
        raise AudioExtractionError(
            "Failed to extract audio from video"
        )
    return output_path

def ingest_media(file_path:str,input_type:str)->dict:
    """Validate,hash,normalize a media file"""
    path = Path(file_path)
    if not path.exists():
        raise InvalidInputError(
            "Media file does not exist"
        )
    validate_file_size(str(path),input_type)
    duration = validate_media_duration(str(path),input_type)
    content_hash = calculate_file_hash(str(path))
    result = {
        "input_type":input_type,
        "content_hash":content_hash,
        "duration_seconds":duration,
        "audio_path":None,
        "media_path":str(path)
    }
    if input_type == "video_file":
        audio_path = extract_audio(str(path))
        result["audio_path"] = str(audio_path)
    return result