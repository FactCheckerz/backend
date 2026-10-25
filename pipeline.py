"""End-to-end orchestration matching the diagram's flow left-to-right."""
from preprocessing import unify_to_text
from claim_extraction import extract_claims
from evidence_resources import refresh_corpus_for_topic
from retrieval import retrieve
from verification import analyze_claim
from fusion import full_output
from progress import step, done


def run_pipeline(raw_input: str, input_type: str = "text") -> dict:
    step(f"=== Pipeline started (input_type={input_type}) ===")
    unified_text = unify_to_text(raw_input, input_type)
    claims = extract_claims(unified_text)

    if not claims:
        done("=== Pipeline finished — no checkable medical claim found. ===")
        return {"claims": [], "message": "No checkable medical claim found."}

    results = []
    for i, claim_obj in enumerate(claims, start=1):
        claim = claim_obj["normalized_claim"]
        step(f"--- Verifying claim {i}/{len(claims)}: \"{claim}\" ---")

        # Pull fresh PubMed evidence for this claim before searching: the LLM's
        # keyword query first, then broader fallbacks if PubMed finds nothing.
        # For denials ("X is fake") search the subject first — the LLM's query
        # tends to include words like "myth" that no paper uses.
        denial_subject = claim_obj.get("denial_subject", "")
        refresh_corpus_for_topic(
            denial_subject,
            claim_obj.get("pubmed_query", ""),
            " ".join(claim_obj.get("medical_entities", [])),
            claim_obj.get("main_topic", ""),
            claim,
        )

        retrieved = retrieve(claim)
        analyzed = analyze_claim(claim, retrieved, relevance_query=denial_subject)
        result = full_output(claim, analyzed, asserts_effect=claim_obj.get("asserts_effect", False))
        result["medical_entities"] = claim_obj.get("medical_entities", [])
        result["main_topic"] = claim_obj.get("main_topic", "")
        result["original_text"] = claim_obj.get("raw_span", "")
        results.append(result)
        done(f"--- Claim {i}/{len(claims)} done. ---")

    done(f"=== Pipeline finished — {len(results)} claim(s) verified. ===")
    return {"claims": results}
