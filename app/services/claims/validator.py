import json
from functools import lru_cache

from app.core.config import (GROQ_API_KEY, GROQ_LLM)
from app.core.claim_review_config import (CLAIM_EDIT_VALIDATOR)

# labels for bart
BART_LABELS = [
    "verifiable factual claim",
    "opinion or subjective statement",
    "question",
    "instruction or command",
    "greeting or conversational statement",
]

@lru_cache(maxsize=1)
def get_bart_classifier():
    """Loading Bart only once"""
    from transformers import pipeline
    return pipeline(
        "zero-shot-classification",
        model="facebook/bart-large-mnli"
    )

def validate_with_bart(claim_text: str) -> dict:
    """verifies if edited claim looks like a factual/verifiable claim"""
    classifier = get_bart_classifier()
    result = classifier(
        claim_text,
        candidate_labels=BART_LABELS,
        multi_label=False
    )

    top_label = result["labels"][0]
    top_score = float(result["scores"][0])

    is_valid = (
        top_label == "verifiable factual claim"
        and top_score >= 0.60
    )

    return {
        "valid": is_valid,
        "method":"bart",
        "label":top_label,
        "score":top_score,
        "reason":(
            "Text is classified as a verifiable factual claim" if is_valid
            else "Edited text does not appear to be a sufficiently verifiable factual claim."
        )
    }

def validate_with_hybrid(claim_text: str) -> dict:
    """verifies if edited claim looks like a factual/verifiable claim
    uses bart + LLM"""
    bart_result = validate_with_bart(claim_text)

    # if bart already rejects api call nako
    if not bart_result["valid"]:
        return {
            **bart_result,
            "method":"hybrid",
            "bart":bart_result,
            "groq":None
        }

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ KEY required for hybrid validation"
        )

    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    prompt = f"""You are validating an edited claim for a fact-checking application.
    Determine whether the text below is a clear,self-contained, factual claim that can reasonably be checked against evidence.
    Return ONLY valid JSON using exactly this structure:
    {{
        "valid": true,
        "reason": "short explanation"
    }}
    Rules:
    - valid=true only if the text states something that could be factually verified.
    - valid=false for opinions, questions, commands, greetings, vague fragments, or purely subjective statements.
    - Do NOT determine whether the claim is true or false.
    - Only determine whether it is suitable for fact-checking.
    Claim:
    {claim_text}"""
    response = client.chat.completions.create(
        model=GROQ_LLM,
        messages=[
            {
                "role":"system",
                "content":(
                    "You classify claims for a fact-checking pipeline"
                )
            },
            {
                "role":"user",
                "content": prompt
            }
        ],
        temperature=0
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```json"):
        raw = raw[len("```json"):]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    try:
        groq_result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Groq returned invalid JSON during claim validation"
        ) from exc

    groq_valid = bool(groq_result.get("valid"))
    return {
        "valid":(bart_result["valid"] and groq_valid),
        "method":"hybrid",
        "label":bart_result["label"],
        "score":bart_result["score"],
        "reason":groq_result.get("reason",""),
        "bart":bart_result,
        "groq":groq_result
    }

def validate_edited_claim(claim_text: str) -> dict:
    if CLAIM_EDIT_VALIDATOR == "bart":
        return validate_with_bart(claim_text)
    return validate_with_hybrid(claim_text)