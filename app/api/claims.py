from fastapi import APIRouter,HTTPException
from app.schemas.claims import AddClaimRequest,ClaimActionResponse,ConfirmClaimsRequest,ConfirmClaimsResponse,EditClaimRequest
from app.services.claims.service import add_claim,confirm_claims,delete_manual_claim,edit_claim,exclude_claim,include_claim,list_claims,restore_claim

router = APIRouter(
    prefix="/claims",
    tags=["Claims"]
)

def handle_error(exc: Exception):
    if isinstance(exc,ValueError):
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )
    raise HTTPException(
        status_code=500,
        detail="Claim Operation Failed"
    )

# get all claims for submission
@router.get("/submission/{submission_id}")
def get_submission_claims(submission_id: str):
    try:
        return {
            "submission_id":submission_id,
            "claims": list_claims(submission_id)
        }
    except Exception as exc:
        handle_error(exc)

# include a particular claim for processing
@router.post("/{claim_id}/include",response_model=ClaimActionResponse)
def include(claim_id: str):
    try:
        return {
            "success":True,
            "message":"Claim included",
            "claim":include_claim(claim_id)
        }
    except Exception as exc:
        handle_error(exc)

# exclude a particular claim from processing
@router.post("/{claim_id}/exclude",response_model=ClaimActionResponse)
def exclude(claim_id: str):
    try:
        return {
            "success": True,
            "message": "Claim excluded",
            "claim": exclude_claim(claim_id)
        }
    except Exception as exc:
        handle_error(exc)

# edit a iddentified claim
@router.put("/{claim_id}")
def edit(claim_id: str, request: EditClaimRequest):
    try:
        result = edit_claim(claim_id,request.claim_text)
        return {
            "success": True,
            "message":"Claim edited successfully",
            **result
        }
    except Exception as exc:
        handle_error(exc)

# restore edited claim back to og
@router.post("/{claim_id}/restore",response_model=ClaimActionResponse)
def restore(claim_id: str):
    try:
        return {
            "success":True,
            "message":"Original Claim restored",
            "claim":restore_claim(claim_id)
        }
    except Exception as exc:
        handle_error(exc)

# add manual claim
@router.post("/submission/{submission_id}/add")
def add(submission_id: str,request: AddClaimRequest):
    try:
        claim = add_claim(submission_id,request.claim_text,request.included)
        return {
            "success":True,
            "message":"Claim added successfully",
            "claim": claim
        }
    except Exception as exc:
        handle_error(exc)

# delete manually added claim
@router.delete("/{claim_id}")
def delete(claim_id: str):
    try:
        delete_manual_claim(claim_id)
        return {
            "success":True,
            "message":"Manual claim deleted successfully"
        }
    except Exception as exc:
        handle_error(exc)

# confirm claim set
@router.post("/confirm",response_model=ConfirmClaimsResponse)
def confirm(request: ConfirmClaimsRequest):
    try:
        included = confirm_claims(request.submission_id)
        return {
            "success":True,
            "submission_id":request.submission_id,
            "included_claims":included
        }
    except Exception as exc:
        handle_error(exc)