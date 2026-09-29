from fastapi import ( APIRouter, File, Form, HTTPException, UploadFile )
from app.schemas.ingestion import ( TextIngestionRequest, URLIngestionRequest )
from app.services.ingestion.exceptions import ( IngestionError )
from app.services.ingestion.media import (save_uploaded_file)
from app.services.ingestion.service import (
    cleanup_media,
    ingest_text_input,
    ingest_uploaded_media,
    ingest_url
)

router = APIRouter(
    prefix="/api/v1/ingest",
    tags=["Ingestion"]
)

@router.post("/text")
def ingest_text_endpoint(request: TextIngestionRequest):
    """Ingest a text input"""
    try:
        result = ingest_text_input(request.text)
        return {
            "status":"success",
            "mode":request.mode,
            "data":result
        }
    except IngestionError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        ) from exc

@router.post("/url")
def ingest_url_endpoint(request: URLIngestionRequest):
    """Download and ingest supported url"""
    result = None
    try:
        result = ingest_url(request.url)
        response = {
            "status":"success",
            "mode":request.mode,
            "data":{
                "input_type":result["input_type"],
                "raw_url":result["raw_url"],
                "content_hash":result["content_hash"],
                "duration_seconds":result["duration_seconds"],
                "title":result.get("title")
            }
        }
        return response
    except IngestionError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        ) from exc
    finally:
        if result:
            cleanup_media(
                result.get("media_path"),
                result.get("audio_path"),
            )

@router.post("/media")
def ingest_media_endpoint(mode: str = Form(...),input_type: str = Form(...),file: UploadFile = File(...)):
    """Ingest uploaded audio or video"""
    if mode not in { "general","medical"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid mode"
        )
    if input_type not in { "audio","video_file" }:
        raise HTTPException(
            status_code=400,
            detail=(
                "input_type must be "
                "'audio' or 'video_file'."
            )
        )
    media_path,audio_path = None,None
    try:
        media_path = save_uploaded_file(
            file.file,input_type,file.filename
        )
        result = ingest_uploaded_media(str(media_path),input_type)
        audio_path = result.get("audio_path")
        return {
            "status":"success",
            "mode":mode,
            "data":{
                "input_type":result["input_type"],
                "content_hash":result["content_hash"],
                "duration_seconds":result["duration_seconds"]
            }
        }
    except IngestionError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    finally:
        cleanup_media(
            str(media_path)
            if media_path
            else None,
            audio_path
        )