"""
Stage 3 — Claim Extraction & NLP.

WHY an LLM instead of the classic BERT-NER + regex pipeline in the diagram:
A WhatsApp forward is rarely one clean sentence — it's often a wall of text
with 2-3 bundled claims, sarcasm, or a claim buried inside a story. Rule-based
claim detection (POS patterns) or a fine-tuned BERT token-classifier only
extracts entities, not the *checkable proposition*. A modern instruction-tuned
LLM (Qwen2.5 / Llama3.2, 2024) does claim decomposition + normalization in one
shot, with reasoning, and needs zero labeled training data.
Without this step: you'd be fact-checking loosely-related keywords instead of
an actual verifiable medical claim, which tanks NLI accuracy downstream no
matter how good the retriever/verifier is.

Runs against a local Ollama server:
    macOS (M5 laptop):  brew install ollama && ollama pull qwen2.5:7b-instruct
    Colab:               !curl -fsSL https://ollama.com/install.sh | sh
                          then run `ollama serve &` and `ollama pull llama3.2:3b`
                          (use the 3B model on Colab's T4 — 8GB is tight once
                          you also load embedding + NLI models on the same GPU)
"""
import json
import ollama
from config import LLM_MODEL

_SYSTEM_PROMPT = """You are a medical claim extraction system. Given a message
(often a WhatsApp/social forward), extract every distinct, independently
checkable medical claim.

Return ONLY valid JSON, no prose, in this exact shape:
{
  "claims": [
    {
      "raw_span": "<verbatim text the claim came from>",
      "normalized_claim": "<claim rewritten as one neutral declarative sentence, preserving the exact polarity/meaning of the original — do NOT negate or correct it, even if it looks false; just restate what is being claimed>",
      "medical_entities": ["<drug/condition/procedure/etc>", ...],
      "claim_type": "causal | statistical | prescriptive | anecdotal"
    }
  ]
}
If there is no checkable medical claim, return {"claims": []}.
"""


def extract_claims(unified_text: str) -> list[dict]:
    response = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": unified_text},
        ],
        format="json",       # Ollama structured-output mode — no brittle regex parsing
        options={"temperature": 0.0},  # deterministic extraction, not creative writing
    )
    try:
        parsed = json.loads(response["message"]["content"])
        return parsed.get("claims", [])
    except (json.JSONDecodeError, KeyError):
        # Fail safe rather than crash the pipeline on a malformed LLM response
        return []


if __name__ == "__main__":
    sample = (
        "Forwarded: Drinking hot water with turmeric every morning cures "
        "diabetes completely within 3 weeks, doctors don't want you to know this!"
    )
    print(json.dumps(extract_claims(sample), indent=2))
