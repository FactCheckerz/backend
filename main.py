"""
FastAPI backend.

WHY FastAPI over Flask here: async support (matters once you add real
concurrent PubMed/network calls), automatic OpenAPI docs at /docs which you
can screenshot straight into your report, and native Pydantic validation so
malformed requests fail fast with a clear error instead of a stack trace deep
in your pipeline.
"""
import os
import tempfile

from fastapi import FastAPI, File, Form, UploadFile
from pydantic import BaseModel
from pipeline import run_pipeline
from media_fetch import download_media

app = FastAPI(
    title="Multimodal Medical Misinformation Detection & Fact Verification API",
    version="0.1.0",
)


class VerifyRequest(BaseModel):
    text: str = ""
    input_type: str = "text"  # "text" | "audio" | "video"
    url: str | None = None  # YouTube/Reel/any yt-dlp-supported link, for audio/video input_type


@app.post("/verify")
def verify(req: VerifyRequest):
    if req.url:
        media_path = download_media(req.url)
        return run_pipeline(media_path, req.input_type)
    return run_pipeline(req.text, req.input_type)


@app.post("/verify/upload")
async def verify_upload(file: UploadFile = File(...), input_type: str = Form(...)):
    suffix = os.path.splitext(file.filename or "")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    return run_pipeline(tmp_path, input_type)


@app.get("/health")
def health():
    return {"status": "ok"}

# Run with: uvicorn main:app --reload --port 8000
