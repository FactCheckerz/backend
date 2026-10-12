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
    response = (supabase.table("submissions").select("*").eq("id",submission_id).single().execute())
    submission = response.data
    if not submission:
        raise HTTPException(
            status_code=404,
            detail="Submission not found"
        )
    raw_text = submission.get("raw_text")
    if not raw_text or not raw_text.strip():
        raise HTTPException(
            status_code=400,
            detail = "Submission does not contain processed text"
        )
    service = ClaimExtractionService()
    candidates = service.extract(raw_text)
    # makes retrying endpoint easier during dev
    (supabase.table("claims").delete().eq("submission_id",submission_id).execute())
    if candidates:
        rows = []
        for candidate in candidates:
            rows.append(
                {
                    "submission_id":submission_id,
                    "claim_text":candidate.claim_text,
                    "original_claim_text": candidate.claim_text,
                    "original_span":candidate.original_span,
                    "included":True
                }
            )
        (supabase.table("claims").insert(rows).execute())

    # updating submission status
    (supabase.table("submissions").update({"status":"claims_ready"}).eq("id",submission_id).execute())

    return ClaimExtractionResponse(
        submission_id=submission_id,
        strategy=CLAIM_EXTRACTION_STRATEGY,
        candidate_claims=candidates,
        count=len(candidates)
    )