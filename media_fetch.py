"""
Downloads a video/audio file from a URL (YouTube, Instagram Reels, TikTok,
or anything yt-dlp supports) so it can be fed into preprocessing.py the same
way an uploaded file is.
"""
import tempfile

import yt_dlp


def download_media(url: str) -> str:
    """Downloads `url` to a temp file (merged to mp4) and returns its local path."""
    tmp_dir = tempfile.mkdtemp()
    out_path = f"{tmp_dir}/media.mp4"
    ydl_opts = {
        "outtmpl": out_path,
        "format": "bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)
    return out_path
