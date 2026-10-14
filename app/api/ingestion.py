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
from app.services.submissions import get_or_create_submission

router = APIRouter(
    prefix="/ingest",
    tags=["Ingestion"]
)

@router.post("/text")
def ingest_text_endpoint(request: TextIngestionRequest):
    """Normalize, cache and persist a text submission"""
    try:
        ingested = ingest_text_input(request.text)
        result = get_or_create_submission(
            ingested_data=ingested,
            mode = request.mode,
        )
        submission = result["submission"]
        return {
            "status":"success",
            "cache_hit":result["cache_hit"],
            "data":{
                "submission_id":submission["id"],
                "input_type":submission["input_type"],
                "mode":submission["mode"],
                "raw_text":submission["raw_text"],
                "status":submission["status"],
            }
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
        stored = get_or_create_submission(
            ingested_data=result,
            mode=request.mode
        )
        submission = stored["submission"]
        response = {
            "status":"success",
            "cache_hit": stored["cache_hit"],
            "data":{
                "submission":submission["id"],
                "input_type":submission["input_type"],
                "mode":submission["mode"],
                "raw_url":submission["raw_url"],
                "duration_seconds":submission["duration_seconds"],
                "raw_text": submission["raw_text"],
                "status":submission["status"]
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
        ingested = ingest_uploaded_media(str(media_path),input_type)
        audio_path = ingested.get("audio_path")
        stored = get_or_create_submission(
            ingested_data=ingested,
            mode=mode
        )
        submission = stored["submission"]
        return {
            "status":"success",
            "cache_hit":stored["cache_hit"],
            "data":{
                "submission_id":submission["id"],
                "input_type":submission["input_type"],
                "mode":submission["mode"],
                "duration_seconds":submission["duration_seconds"],
                "raw_text": submission["raw_text"],
                "status":submission["status"]
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