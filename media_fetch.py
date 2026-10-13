"""
Downloads a video/audio file from a URL (YouTube, Instagram Reels, TikTok,
or anything yt-dlp supports) so it can be fed into preprocessing.py the same
way an uploaded file is.
"""
import tempfile

import yt_dlp

from progress import step, done


def _progress_hook(d: dict):
    if d["status"] == "downloading":
        pct = d.get("_percent_str", "").strip()
        speed = d.get("_speed_str", "").strip()
        step(f"  Downloading media... {pct} at {speed}")
    elif d["status"] == "finished":
        step("  Download finished, merging streams...")


def download_media(url: str) -> str:
    """Downloads `url` to a temp file (merged to mp4) and returns its local path."""
    step(f"Fetching media from URL: {url}")
    tmp_dir = tempfile.mkdtemp()
    out_path = f"{tmp_dir}/media.mp4"
    ydl_opts = {
        "outtmpl": out_path,
        "format": "bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
        "progress_hooks": [_progress_hook],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)
    done(f"Media downloaded to {out_path}.")
    return out_path
