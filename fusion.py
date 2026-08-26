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
from config import LLM_MODEL

_EXPLANATION_PROMPT = """You are a medical fact-checking assistant. Given a
claim, a verdict, and supporting/contradicting evidence snippets, write a
concise (3-5 sentence) plain-language explanation for a general audience.
Cite the evidence sources by name inline. Do not invent evidence beyond what
is given. Do not soften a FALSE verdict to be polite.

Claim: {claim}
Verdict: {verdict}
Evidence:
{evidence_block}
"""


def fuse_verdict(evidence: list[dict]) -> dict:
    if not evidence:
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

    return {
        "verdict": verdict,
        "confidence": round(float(confidence), 3),
        "evidence_strength": round(float(total_strength), 3),
        "supporting_count": len(support),
        "contradicting_count": len(contradict),
    }


def generate_explanation(claim: str, verdict_info: dict, evidence: list[dict]) -> str:
    evidence_block = "\n".join(
        f"- [{e['nli_label'].upper()}, conf={e['nli_confidence']:.2f}] "
        f"({e.get('source', 'unknown')}) {e['text'][:300]}"
        for e in evidence
    )
    prompt = _EXPLANATION_PROMPT.format(
        claim=claim, verdict=verdict_info["verdict"], evidence_block=evidence_block
    )
    response = ollama.chat(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.3},
    )
    return response["message"]["content"]


def full_output(claim: str, evidence: list[dict]) -> dict:
    verdict_info = fuse_verdict(evidence)
    explanation = generate_explanation(claim, verdict_info, evidence)
    citations = [
        {"source": e.get("source"), "url": e.get("url")}
        for e in evidence if e["nli_label"] in ("entailment", "contradiction")
    ]
    return {
        "claim": claim,
        **verdict_info,
        "explanation": explanation,
        "citations": citations,
        "evidence_detail": evidence,
    }
