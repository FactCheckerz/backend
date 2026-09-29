from pathlib import Path
import shutil

from app.services.ingestion.media import ( ingest_media )
from app.services.ingestion.text import ( ingest_text )
from app.services.ingestion.url import ( download_video )

def cleanup_media(*file_paths: str | None) -> None:
    """Delete temp media files"""
    for file_path in file_paths:
        if not file_path:
            continue
        path = Path(file_path)
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass

def ingest_text_input(text:str) -> dict:
    """ingest a text submission"""
    return ingest_text(text)

def ingest_uploaded_media(file_path: str,input_type: str) -> dict:
    """ingest uploaded audio/video"""
    return ingest_media(file_path,input_type)

def ingest_url(url: str) -> dict:
    """downloads and ingest a supported video url"""
    download_result = download_video(url)
    media_path = download_result["media_path"]
    try:
        result = ingest_media(media_path,"video_file")
        result["input_type"] = "video_url"
        result["raw_url"] = url
        result["title"] = download_result.get("title")
        return result
    except Exception:
        cleanup_media(media_path)
        raise