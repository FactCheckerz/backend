from pathlib import Path
from urllib.parse import urlparse
import yt_dlp

from app.core.config import (
    MAX_VIDEO_SIZE_MB,
    TEMP_MEDIA_DIR
)

from app.services.ingestion.exceptions import (
    DownloadError,
    InvalidInputError,
    MediaTooLargeError,
)
ALLOWED_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "www.youtu.be",

    "instagram.com",
    "www.instagram.com",

    "facebook.com",
    "www.facebook.com",
    "fb.watch",
}

def validate_url(url: str) -> None:
    """Validates whether url belongs to one of the supported platform"""
    if not url:
        raise InvalidInputError(
            "URL cannot be empty"
        )
    parsed = urlparse(url)
    if parsed.scheme not in { "http","https" }:
        raise InvalidInputError(
            "URL must use HTTP or HTTPS"
        )
    hostname = (parsed.hostname or "").lower()
    if hostname not in ALLOWED_DOMAINS:
        raise InvalidInputError(
            "Unsupported URL platform. "
            "Only YouTube, Instagram, and Facebook "
            "URLs are supported."
        )

def download_video(url: str) -> dict:
    """downloads supported social-media video"""
    validate_url(url)

    Path(TEMP_MEDIA_DIR).mkdir(
        parents=True,
        exist_ok=True
    )

    output_template = str(
        Path(TEMP_MEDIA_DIR) / "%(id)s.%(ext)s"
    )

    max_filesize = (
        MAX_VIDEO_SIZE_MB * 1024 * 1024
    )

    options = {
        "outtmpl":output_template,
        "format":(
            "bestvideo+bestaudio/"
            "best"
        ),
        "merge_output_format":"mp4",
        "noplaylist":True,
        "max_filesize":max_filesize,
        "quiet":True,
        "no_warnings":True
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(
                url,
                download=True,
            )
            downloaded_path = Path(
                ydl.prepare_filename(info)
            )
            if not downloaded_path.exists():
                possible_mp4 = (
                    downloaded_path.with_suffix(
                        ".mp4"
                    )
                )
                if possible_mp4.exists():
                    downloaded_path = (
                        possible_mp4
                    )

            if not downloaded_path.exists():
                raise DownloadError(
                    "Download video file"
                    "Could not be located"
                )

            return {
                "url":url,
                "title":info.get("title"),
                "duration_seconds":info.get("duration"),
                "media_path":str(downloaded_path)
            }
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(
            f"Failed to download URL: {exc}"
        ) from exc   