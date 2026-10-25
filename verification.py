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

2. NLI model (DeBERTa-v3, 3-way): "does this evidence SUPPORT,
   CONTRADICT, or say nothing (NEUTRAL) about the claim?"
   This is the actual verification signal — relevance alone doesn't tell you
   if the evidence agrees or disagrees with the claim.

WHY sentence-level NLI instead of feeding the whole abstract:
NLI models are trained on single-sentence premises. A 300-word abstract as
the premise almost always comes out "neutral" — the one sentence that
actually supports or refutes the claim gets drowned out (and long abstracts
get truncated at 512 tokens anyway). So each abstract is split into
sentences, every sentence is checked against the claim, and the most
decisive sentence speaks for that abstract.
"""
import re

from sentence_transformers import CrossEncoder
from config import RERANKER_MODEL, NLI_MODEL, DEVICE, TOP_K_AFTER_RERANK
from progress import step, done

step(f"Loading reranker model {RERANKER_MODEL} (device={DEVICE}, first time only)...")
# Default max_length for bge-reranker-v2-m3 is 8192 tokens — capping it at 512
# makes reranking several times faster with no real loss on abstract-length text.
_reranker = CrossEncoder(RERANKER_MODEL, device=DEVICE, max_length=512)
done("Reranker model loaded.")

step(f"Loading NLI model {NLI_MODEL} (device={DEVICE}, first time only)...")
_nli = CrossEncoder(NLI_MODEL, device=DEVICE)  # (premise, hypothesis) -> label probs
done("NLI model loaded.")

# Read label order from the model itself rather than hardcoding it — different
# checkpoints order (and even count) their labels differently.
_NLI_LABELS = [_nli.model.config.id2label[i].lower() for i in range(len(_nli.model.config.id2label))]
if not {"entailment", "neutral", "contradiction"} <= set(_NLI_LABELS):
    raise ValueError(f"{NLI_MODEL} is not a 3-way NLI model (labels: {_NLI_LABELS})")

_MIN_SENTENCE_CHARS = 25


def _split_sentences(text: str) -> list[str]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text)]
    return [s for s in sentences if len(s) >= _MIN_SENTENCE_CHARS] or [text]


def rerank(claim: str, evidence: list[dict], relevance_query: str = "") -> list[dict]:
    """relevance_query: optional extra query (e.g. a denial's subject); each
    doc keeps the higher of its two relevance scores."""
    step(f"Reranking {len(evidence)} evidence candidate(s) for relevance...")
    scores = _reranker.predict([(claim, e["text"]) for e in evidence])
    if relevance_query:
        alt = _reranker.predict([(relevance_query, e["text"]) for e in evidence])
        scores = [max(s, a) for s, a in zip(scores, alt)]
    for e, s in zip(evidence, scores):
        e["relevance_score"] = float(s)
    ranked = sorted(evidence, key=lambda e: e["relevance_score"], reverse=True)
    top = ranked[:TOP_K_AFTER_RERANK]
    done(f"Reranking complete — keeping top {len(top)}.")
    return top


def check_entailment(claim: str, evidence: list[dict]) -> list[dict]:
    """evidence sentence -> premise, claim -> hypothesis (standard NLI
    direction: does the evidence entail the claim?)."""
    step(f"Stage 5: running sentence-level NLI on {len(evidence)} evidence piece(s)...")
    sentences_per_doc = [_split_sentences(e["text"]) for e in evidence]
    pairs = [(s, claim) for sentences in sentences_per_doc for s in sentences]
    all_probs = _nli.predict(pairs, apply_softmax=True, batch_size=16) if pairs else []

    i = 0
    for e, sentences in zip(evidence, sentences_per_doc):
        doc_probs = all_probs[i:i + len(sentences)]
        i += len(sentences)
        # The most decisive sentence (strongest support OR contradiction) represents the doc.
        decisive = [
            max(p[_NLI_LABELS.index("entailment")], p[_NLI_LABELS.index("contradiction")])
            for p in doc_probs
        ]
        best = max(range(len(sentences)), key=decisive.__getitem__)
        probs = doc_probs[best]
        label_idx = probs.argmax()
        e["nli_label"] = _NLI_LABELS[label_idx]
        e["nli_confidence"] = float(probs[label_idx])
        e["nli_probs"] = {lbl: float(p) for lbl, p in zip(_NLI_LABELS, probs)}
        e["evidence_sentence"] = sentences[best]
    done("Stage 5 complete.")
    return evidence


def analyze_claim(claim: str, retrieved_evidence: list[dict], relevance_query: str = "") -> list[dict]:
    top_evidence = rerank(claim, retrieved_evidence, relevance_query)
    return check_entailment(claim, top_evidence)
