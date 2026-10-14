from fastapi import APIRouter,HTTPException
from app.core.claim_extraction_config import CLAIM_EXTRACTION_STRATEGY
from app.core.supabase import supabase
from app.schemas.claim_extraction import ClaimExtractionResponse
from app.services.claims.extraction_service import ClaimExtractionService

router = APIRouter(
    prefix="/claims",
    tags=["Claim Extraction"]
)

@router.post("/extract/{submission_id}",response_model=ClaimExtractionResponse)
def extract_claims(submission_id: str):
    submission_result = (supabase.table("submissions").select("*").eq("id",submission_id).limit(1).execute())
    submissions = submission_result.data or []
    if not submissions:
        raise HTTPException(
            status_code=404,
            detail="Submission not found"
        )
    submission = submissions[0]
    raw_text = submission.get("raw_text")
    if not raw_text or not raw_text.strip():
        raise HTTPException(
            status_code=400,
            detail = "Submission does not contain processed text"
        )
    existing_claims = (
        supabase.table("claims").select("id").eq("submission_id",submission_id).limit(1).execute().data or []
    )
    if existing_claims:
        raise HTTPException(
            status_code=409,
            detail = "Candidate claims already been extracted for this submission. Use claim review endpoint"
        )
    service = ClaimExtractionService()
    candidates = service.extract(raw_text)
    if not candidates:
        (supabase.table("submissions").delete().eq("id",submission_id).execute())
        raise HTTPException(
            status_code=422,
            detail="No verifiable candidate claims were detected, temporary submission row deleted"
        )
    if candidates:
        rows = [
            {
                "submission_id":submission_id,
                "claim_text": candidate.claim_text,
                "original_claim_text": candidate.claim_text,
                "original_span": candidate.original_span,
                "included":True,
                "is_manual":False,
            }
            for candidate in candidates
        ]
        supabase.table("claims").insert(rows).execute()
    supabase.table("submissions").update({"status":"claims_ready"}).eq("id",submission_id).execute()
    return ClaimExtractionResponse(
        submission_id=submission_id,
        strategy=CLAIM_EXTRACTION_STRATEGY,
        candidate_claims=candidates,
        count=len(candidates)
    )