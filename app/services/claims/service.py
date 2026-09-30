from uuid import UUID
from app.core.supabase import supabase
from app.services.claims.validator import ( validate_edited_claim )

def _get_claim(claim_id: str) -> dict:
    """get one claim from supabase"""
    result = (supabase.table("claims").select("*").eq("id",claim_id).limit(1).execute())
    if not result.data:
        raise ValueError("Claim not found")
    return result.data[0]

def list_claims(submission_id: str) -> list[dict]:
    result = (supabase.table("claims").select("*").eq("submission_id",submission_id).order("created_at").execute())
    return result.data or []

def include_claim(claim_id: str) -> dict:
    _get_claim(claim_id)
    result = (supabase.table("claims").update({"included":True}).eq("id",claim_id).execute())
    return result.data[0]

def exclude_claim(claim_id: str) -> dict:
    _get_claim(claim_id)
    result = (supabase.table("claims").update({"included":False}).eq("id",claim_id).execute())
    return result.data[0]

def edit_claim(claim_id: str,new_text: str) -> dict:
    claim = _get_claim(claim_id)
    cleaned = " ".join(new_text.split())
    if not cleaned:
        raise ValueError("Claim caanot be empty")

    #validation nlp
    validation = validate_edited_claim(cleaned)
    if not validation["valid"]:
        raise ValueError(
            "Edited claim failed NLP test"
            f"validation: {validation['reason']}"
        )
    update_data = {
        "claim_text": cleaned
    }
    if not claim.get("original_claim_text"):
        update_data["original_claim_text"] = claim["claim_text"]

    result = supabase.table("claims").update(update_data).eq("id",claim_id).execute()
    return {
        "claim":result.data[0],
        "validation":validation
    }

def restore_claim(claim_id: str) -> dict:
    claim = _get_claim(claim_id)
    original = claim.get("original_claim_text")
    if not original:
        raise ValueError("Original claim text is not available")
    result = supabase.table("claims").update({"claim_text":original}).eq("id",claim_id).execute()
    return result.data[0]

def add_claim(submission_id: str, claim_text: str, included: bool) -> dict:
    cleaned = " ".join(claim_text.split())
    if not cleaned:
        raise ValueError("Claim cannot be empty")
    row = {
        "submission_id": str(UUID(submission_id)),
        "claim_text": cleaned,
        "original_claim_text": cleaned,
        "original_span": None,
        "included": included,
        "is_manual": True
    }
    result = (supabase.table("claims").insert(row).execute())
    return result.data[0]

def delete_manual_claim(claim_id: str) -> None:
    claim = _get_claim(claim_id)
    if not claim.get("is_manual",False):
        raise ValueError(
            "Detected claims cannot be deleted exclude it instead only manually added claims can be deleted"
        )
    (supabase.table("claims").delete().eq("id",claim_id).execute())

def confirm_claims(submission_id: str) -> list[dict]:
    claims = list_claims(submission_id)
    included_claims = [claim for claim in claims if claim.get("included",True)]
    if not included_claims:
        raise ValueError("At least one claim must be included")
    (supabase.table("submissions").update({"status":"claims_ready"}).eq("id",submission_id).execute())
    return included_claims


