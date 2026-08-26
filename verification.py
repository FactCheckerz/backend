"""
Stage 5 — Evidence Analysis (Deep Learning core of the project).

Two separate cross-encoders, doing two separate jobs — don't collapse them
into one model, they optimize for different things:

1. Reranker (bge-reranker-v2-m3): "is this evidence *relevant* to the claim?"
   Bi-encoder retrieval (Stage 4) is fast but approximate; a cross-encoder
   that attends jointly over (claim, evidence) is slower but far more
   accurate at relevance — standard two-stage retrieve-then-rerank pattern.
   Without reranking: your top-k evidence is "close enough" semantically but
   the NLI step ends up reasoning over weakly-related text.

2. NLI model (DeBERTa-v3 zeroshot-v2): "does this evidence SUPPORT,
   CONTRADICT, or say nothing (NEUTRAL) about the claim?"
   This is the actual verification signal — relevance alone doesn't tell you
   if the evidence agrees or disagrees with the claim.
"""
from sentence_transformers import CrossEncoder
from config import RERANKER_MODEL, NLI_MODEL, DEVICE, TOP_K_AFTER_RERANK

_reranker = CrossEncoder(RERANKER_MODEL, device=DEVICE)
_nli = CrossEncoder(NLI_MODEL, device=DEVICE)  # trained with (premise, hypothesis) -> [entail, neutral, contra]
_NLI_LABELS = ["entailment", "neutral", "contradiction"]


def rerank(claim: str, evidence: list[dict]) -> list[dict]:
    pairs = [(claim, e["text"]) for e in evidence]
    scores = _reranker.predict(pairs)
    for e, s in zip(evidence, scores):
        e["relevance_score"] = float(s)
    ranked = sorted(evidence, key=lambda e: e["relevance_score"], reverse=True)
    return ranked[:TOP_K_AFTER_RERANK]


def check_entailment(claim: str, evidence: list[dict]) -> list[dict]:
    """evidence -> premise, claim -> hypothesis (standard NLI direction:
    does the evidence entail the claim?)."""
    pairs = [(e["text"], claim) for e in evidence]
    logits = _nli.predict(pairs, apply_softmax=True)
    for e, probs in zip(evidence, logits):
        label_idx = probs.argmax()
        e["nli_label"] = _NLI_LABELS[label_idx]
        e["nli_confidence"] = float(probs[label_idx])
        e["nli_probs"] = {lbl: float(p) for lbl, p in zip(_NLI_LABELS, probs)}
    return evidence


def analyze_claim(claim: str, retrieved_evidence: list[dict]) -> list[dict]:
    top_evidence = rerank(claim, retrieved_evidence)
    return check_entailment(claim, top_evidence)
