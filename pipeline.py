"""End-to-end orchestration matching the diagram's flow left-to-right."""
from preprocessing import unify_to_text
from claim_extraction import extract_claims
from evidence_resources import refresh_corpus_for_topic
from retrieval import retrieve
from verification import analyze_claim
from fusion import full_output


def run_pipeline(raw_input: str, input_type: str = "text") -> dict:
    unified_text = unify_to_text(raw_input, input_type)
    claims = extract_claims(unified_text)

    if not claims:
        return {"claims": [], "message": "No checkable medical claim found."}

    results = []
    for claim_obj in claims:
        claim = claim_obj["normalized_claim"]

        # Pull fresh PubMed evidence for this specific claim's topic before searching.
        refresh_corpus_for_topic(claim)

        retrieved = retrieve(claim)
        analyzed = analyze_claim(claim, retrieved)
        result = full_output(claim, analyzed)
        result["medical_entities"] = claim_obj.get("medical_entities", [])
        results.append(result)

    return {"claims": results}
