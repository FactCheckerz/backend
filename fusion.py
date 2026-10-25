"""
Stage 6 — Verification & Decision (Decision Fusion Engine + Scoring)
Stage 7 — Explanation (AI-generated explanation, grounded in retrieved evidence)

WHY rule-based fusion over evidence votes, NOT another black-box classifier:
For a fact-checking system, the verdict logic needs to be *explainable* —
you must be able to say "3 of 4 pieces of evidence contradicted this claim,
average confidence 0.82" rather than "a model said so." A learned fusion
classifier is a fine future extension (train on FEVER/PubHealth-style labels)
but for the capstone, transparent aggregation is both easier to defend in a
viva and methodologically more honest given the tiny amount of labeled
misinformation-verdict data you're likely to have.
"""
import ollama
from config import LLM_MODEL, MIN_RELEVANCE
from progress import step, done

_EXPLANATION_PROMPT = """You are a medical fact-checking assistant. Given a
claim, a verdict, and supporting/contradicting evidence snippets, write a
concise (3-5 sentence) plain-language explanation for a general audience.
Cite the evidence sources by name inline. Do not invent evidence beyond what
is given. Do not soften a FALSE verdict to be polite. Start directly with
the explanation — no preamble like "Here's a concise explanation:".

Claim: {claim}
Verdict: {verdict}
Evidence:
{evidence_block}
"""

# Used when no relevant evidence was found. Handing the LLM the irrelevant
# abstracts instead just makes it summarise unrelated studies.
_NO_EVIDENCE_PROMPT = """You are a medical fact-checking assistant. A search of
the PubMed research database found no studies relevant to this claim:

Claim: {claim}

Write 2-3 plain-language sentences for a general audience. {guidance} Do not
invent or cite any studies. Start directly — no preamble.
"""
_NO_EVIDENCE_EFFECT = (
    "Say plainly that there is no scientific evidence supporting this claim, "
    "so it should not be relied on, and suggest checking with a doctor before "
    "trying it."
)
_NO_EVIDENCE_NEUTRAL = (
    "Say that we could not find enough research to confirm or refute it, and "
    "suggest checking with a doctor or a trusted health source."
)
NO_SUPPORT_NOTE = "No scientific evidence supports this claim"
NOT_ENOUGH_NOTE = "Not enough evidence found to confirm or refute this claim"


def fuse_verdict(evidence: list[dict]) -> dict:
    step("Stage 6: fusing NLI votes into a verdict...")
    evidence = [e for e in evidence if e["relevance_score"] >= MIN_RELEVANCE]
    if not evidence:
        done("No evidence — verdict Unverified.")
        return {"verdict": "Unverified", "confidence": 0.0, "evidence_strength": 0.0}

    support = [e for e in evidence if e["nli_label"] == "entailment"]
    contradict = [e for e in evidence if e["nli_label"] == "contradiction"]

    support_strength = sum(e["nli_confidence"] * e["relevance_score"] for e in support)
    contradict_strength = sum(e["nli_confidence"] * e["relevance_score"] for e in contradict)
    total_strength = support_strength + contradict_strength

    if total_strength < 0.3:
        verdict = "Unverified"
        confidence = 1 - total_strength
    elif support_strength > 2 * contradict_strength:
        verdict = "True"
        confidence = support_strength / (total_strength or 1)
    elif contradict_strength > 2 * support_strength:
        verdict = "False"
        confidence = contradict_strength / (total_strength or 1)
    else:
        verdict = "Misleading / Partially True"
        confidence = 1 - abs(support_strength - contradict_strength) / (total_strength or 1)

    result = {
        "verdict": verdict,
        "confidence": round(float(confidence), 3),
        "evidence_strength": round(float(total_strength), 3),
        "supporting_count": len(support),
        "contradicting_count": len(contradict),
    }
    done(f"Verdict: {verdict} (confidence {result['confidence']:.0%}).")
    return result


def generate_explanation(claim: str, verdict_info: dict, evidence: list[dict], asserts_effect: bool = False) -> str:
    step(f"Stage 7: generating explanation via {LLM_MODEL} (Ollama)...")
    if evidence:
        evidence_block = "\n".join(
            f"- [{e['nli_label'].upper()}, conf={e['nli_confidence']:.2f}] "
            f"({e.get('source', 'unknown')}) {e.get('evidence_sentence') or e['text'][:300]}"
            for e in evidence
        )
        prompt = _EXPLANATION_PROMPT.format(
            claim=claim, verdict=verdict_info["verdict"], evidence_block=evidence_block
        )
    else:
        guidance = _NO_EVIDENCE_EFFECT if asserts_effect else _NO_EVIDENCE_NEUTRAL
        prompt = _NO_EVIDENCE_PROMPT.format(claim=claim, guidance=guidance)
    response = ollama.chat(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.3},
    )
    done("Stage 7 complete.")
    return response["message"]["content"]


def full_output(claim: str, evidence: list[dict], asserts_effect: bool = False) -> dict:
    """asserts_effect: the claim says something cures/causes/delays/boosts...
    For those, finding no research IS the answer ("no scientific evidence
    supports this"), unlike e.g. a symptom claim, where it just means we
    couldn't tell."""
    verdict_info = fuse_verdict(evidence)
    relevant = [e for e in evidence if e["relevance_score"] >= MIN_RELEVANCE]
    if verdict_info["verdict"] == "Unverified":
        verdict_info["verdict_note"] = NO_SUPPORT_NOTE if asserts_effect else NOT_ENOUGH_NOTE
        # Relevant-but-weak evidence still goes to the normal prompt; none at all
        # gets the no-evidence prompt.
        explanation = generate_explanation(claim, verdict_info, relevant, asserts_effect)
    else:
        explanation = generate_explanation(claim, verdict_info, relevant or evidence)
    citations = [
        {"source": e.get("source"), "url": e.get("url")}
        for e in evidence
        if e["nli_label"] in ("entailment", "contradiction") and e["relevance_score"] >= MIN_RELEVANCE
    ]
    return {
        "claim": claim,
        **verdict_info,
        "explanation": explanation,
        "citations": citations,
        "evidence_detail": evidence,
    }
