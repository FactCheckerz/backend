from pydantic import BaseModel, Field

class EditClaimRequest(BaseModel):
    claim_text: str = Field(...,min_length=10,max_length=2000)

class AddClaimRequest(BaseModel):
    claim_text: str = Field(...,min_length=10,max_length=2000)

class ClaimActionResponse(BaseModel):
    success: bool
    message: str
    claim: dict

class ConfirmClaimsRequest(BaseModel):
    submission_id: str

class ConfirmClaimsResponse(BaseModel):
    success: bool
    submission_id: str
    included_claims: list[dict]