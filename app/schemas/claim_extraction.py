from pydantic import BaseModel,Field
from typing import List,Optional

class CandidateClaim(BaseModel):
    claim_text: str
    original_span: str
    confidence: Optional[float] = None

class ClaimExtractionResponse(BaseModel):
    submission_id: str
    strategy: str
    candidate_claims: List[CandidateClaim]
    count: int