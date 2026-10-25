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
import re

import ollama
from config import LLM_MODEL
from progress import step, done

_SYSTEM_PROMPT = """You are a medical claim extraction system. Given a message
(often a WhatsApp/social forward, or the transcript + on-screen text of a
video), extract the distinct medical claims a viewer could be misled by.

Step 1 — identify the MAIN TOPIC of the whole message (the disease, drug,
remedy or procedure it is about). Transcripts are often lists ("any pain in
the breast", "swollen lymph nodes") whose subject is only stated once at the
start — every claim inherits that subject.

Step 2 — extract claims. Each claim must:
- be SELF-CONTAINED: understandable and checkable with no other context.
  Always name the main topic and the relationship explicitly.
  BAD:  "Any pain in the breast or nipples."
  GOOD: "Pain in the breast or nipples can be a symptom of breast cancer."
- assert something about health: a cause, risk factor, symptom, diagnosis,
  treatment, cure, prevention, dosage, or side effect — OR deny/dismiss one
  ("period pain is fake", "diabetes is not a real disease", "COVID is a
  hoax"). Denials are claims too and must be extracted.
- preserve the exact polarity/meaning of the original — do NOT negate or
  correct it, even if it looks false; just restate what is being claimed.
  "Period pain is fake" stays "Period pain is fake", never "Period pain is real"
  or "Period pain is a symptom of X".

Do NOT extract:
- background / news-style context or statistics that only introduce the
  topic (e.g. "cases of X are rising in the US"), unless the message's main
  point IS that statistic
- generic advice with no factual content ("talk to your doctor", "stay safe")
- greetings, calls to action, opinions, or the speaker's personal story
Merge near-duplicates into one claim. Extract at most 6 claims, most
important first.

For each claim also write "pubmed_query": 2-6 medical keywords (no full
sentences, no stopwords) that would find research papers on it, e.g.
"breast cancer nipple retraction symptom".

Return ONLY valid JSON, no prose, in this exact shape:
{
  "main_topic": "<e.g. breast cancer>",
  "claims": [
    {
      "raw_span": "<verbatim text the claim came from>",
      "normalized_claim": "<self-contained declarative sentence>",
      "pubmed_query": "<keywords>",
      "medical_entities": ["<drug/condition/procedure/etc>", ...],
      "claim_type": "causal | symptom | treatment | prevention | statistical | prescriptive"
    }
  ]
}
If there is no checkable medical claim, return {"main_topic": "", "claims": []}.
"""


_REFINE_PROMPT = """You are refining one medical claim pulled from a message
whose main topic is: {topic}

Message (for context):
\"\"\"{text}\"\"\"

Extracted claim: "{claim}"

1. Rewrite it as ONE self-contained, checkable sentence that names the main
   topic. Use the relationship the MESSAGE states or clearly implies — never
   invent a different one. Keep the original meaning and polarity — do not
   correct it. If the claim already names the topic and makes sense alone,
   return it unchanged.
   Examples:
   "Nipple retraction." -> "Nipple retraction can be a symptom of breast cancer."
   "Checking for lumps is important." -> "Checking for breast lumps helps detect breast cancer early."
   "Take it every morning." (message: turmeric cures diabetes) -> "Taking turmeric every morning cures diabetes."
2. Classify it into exactly one "category" (do NOT judge whether it is true):
   - "health_claim": says something causes, cures, treats, prevents, is a
     symptom of, or is a risk factor for a condition — or denies that a
     condition/symptom/treatment is real. True OR false — e.g. "turmeric
     cures diabetes", "nipple retraction is a symptom of breast cancer" and
     "period pain is fake" are all health_claim.
   - "background": statistics/news that just introduce the topic, e.g.
     "breast cancer cases are rising among younger women in the US".
   - "generic_advice": an instruction with no factual content, e.g. "talk to
     your doctor", "stay safe", "share this message".
   - "other": conspiracy framing, opinions, greetings, e.g. "doctors don't
     want you to know this".
3. Write "pubmed_query": 2-6 medical keywords to find research papers on it.

Return ONLY JSON: {{"claim": "...", "category": "health_claim", "pubmed_query": "..."}}
"""

_MAX_CLAIMS = 6
_MAX_CONTEXT_CHARS = 3000

# Words that carry a claim's polarity. If the original has one and the
# rewrite doesn't, the rewrite changed what is being claimed.
_POLARITY_WORDS = {
    "not", "no", "never", "fake", "myth", "hoax", "false", "untrue", "scam",
    "lie", "isn't", "doesn't", "don't", "aren't", "can't", "cannot", "won't",
}
_STOP = {"the", "and", "for", "with", "from", "that", "this", "disease", "condition"}

# Claims asserting or denying an effect are what misinformation looks like —
# never let the LLM's category label drop one of these.
_SUBSTANTIVE = re.compile(
    r"\b(cure[sd]?|caus\w*|treat\w*|prevent\w*|heal\w*|kill\w*|reverse[sd]?|"
    r"delay\w*|induc\w*|boost\w*|detox\w*|reduc\w*|lower\w*|increas\w*|"
    r"improv\w*|protect\w*|stop\w*|eliminat\w*|"
    r"fake|hoax|myth|not real|doesn'?t exist|dangerous|harmful|safe)\b",
    re.IGNORECASE,
)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z']+", text.lower()))


def _mentions_topic(claim_text: str, topic: str) -> bool:
    """True if the claim already names the main topic — i.e. it isn't a
    fragment like "Nipple retraction." and needs no contextual rewrite."""
    topic_words = {w for w in _words(topic) if len(w) > 2 and w not in _STOP}
    # ALL topic words: "Pain in the breast" mentions "breast" but not "breast cancer".
    return topic_words <= _words(claim_text)


def _drops_polarity(original: str, rewrite: str) -> bool:
    return bool((_words(original) & _POLARITY_WORDS) - _words(rewrite))


def _denial_subject(claim: dict, topic: str) -> str:
    """For a denial ("Period pain is fake", "Diabetes is not a real disease"),
    return its subject ("period pain"), else "". No paper states "diabetes is
    real", so the reranker scores every abstract as irrelevant to the denial
    sentence (~0.01) even though the NLI model rightly finds they contradict
    it. Relevance and the PubMed search use the subject instead."""
    text = claim["normalized_claim"]
    if not _words(text) & _POLARITY_WORDS:
        return ""
    entities = claim.get("medical_entities") or []
    if isinstance(entities, list) and entities:
        return " ".join(map(str, entities))
    if topic:
        return topic
    # "Period pain is fake" -> "Period pain"
    return re.split(r"\b(?:is|are|was|were|does|do|can|has|have)\b", text, maxsplit=1, flags=re.IGNORECASE)[0].strip()


def _refine_claim(claim: dict, topic: str, text: str, allow_skip: bool) -> dict | None:
    """Second, single-claim LLM pass. Small models (llama3.2:3b) often ignore
    the 'self-contained' rule when extracting many claims at once — e.g. a
    symptom list comes back as bare fragments ("Nipple retraction."), which
    the NLI model can't verify. One focused rewrite per claim is far more
    reliable. Returns None if the claim isn't worth checking.

    The rewrite is only ADOPTED for fragments (claims that don't mention the
    topic) and only if it keeps the original's negation words — small models
    otherwise "improve" claims into different ones, e.g. "Period pain is
    fake" -> "Period pain is a symptom of endometriosis", which then gets
    checked and marked True. Verifying the wrong claim is worse than
    verifying a clumsily-worded one."""
    response = ollama.chat(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": _REFINE_PROMPT.format(
            topic=topic or "unknown", text=text[:_MAX_CONTEXT_CHARS], claim=claim["normalized_claim"],
        )}],
        format="json",
        options={"temperature": 0.0},
    )
    try:
        refined = json.loads(response["message"]["content"])
    except (json.JSONDecodeError, KeyError):
        return claim  # keep the original rather than lose the claim
    # A named category instead of a yes/no "worth checking?" — asked yes/no,
    # small models skip claims because they look *false*, which is backwards.
    category = refined.get("category", "health_claim")
    if category != "health_claim" and allow_skip and not _SUBSTANTIVE.search(claim["normalized_claim"]):
        step(f"  Skipping ({category}): \"{claim['normalized_claim']}\"")
        return None

    original = claim["normalized_claim"]
    rewrite = refined.get("claim")
    if rewrite and rewrite != original:
        if _mentions_topic(original, topic):
            pass  # already self-contained — keep the user's wording
        elif _drops_polarity(original, rewrite):
            step(f"  Rejected rewrite (changed meaning): \"{rewrite}\"")
        else:
            claim["normalized_claim"] = rewrite
    if refined.get("pubmed_query"):
        claim["pubmed_query"] = refined["pubmed_query"]
    return claim


def extract_claims(unified_text: str) -> list[dict]:
    """Each returned claim also carries the message-level "main_topic", so
    downstream stages can fall back to it (e.g. a broader PubMed search)."""
    step(f"Stage 3: extracting medical claims via {LLM_MODEL} (Ollama)...")
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
        main_topic = parsed.get("main_topic", "")
        claims = [c for c in parsed.get("claims", []) if c.get("normalized_claim")]
    except (json.JSONDecodeError, KeyError, AttributeError):
        # Fail safe rather than crash the pipeline on a malformed LLM response
        main_topic, claims = "", []
    done(f"Topic \"{main_topic}\", {len(claims)} candidate claim(s) — refining each...")

    refined_claims = []
    for c in claims:
        if len(refined_claims) == _MAX_CLAIMS:
            break
        # A one-claim message IS the thing the user wants checked — never skip it.
        c = _refine_claim(c, main_topic, unified_text, allow_skip=len(claims) > 1)
        if c:
            c["main_topic"] = main_topic
            c["denial_subject"] = _denial_subject(c, main_topic)
            # Remedy/effect claims: finding no research is itself the answer.
            c["asserts_effect"] = bool(_SUBSTANTIVE.search(c["normalized_claim"]))
            refined_claims.append(c)
    claims = refined_claims
    for c in claims:
        step(f"  Claim: \"{c['normalized_claim']}\"")
    done(f"Stage 3 complete — {len(claims)} claim(s) to verify.")
    return claims


if __name__ == "__main__":
    sample = (
        "Forwarded: Drinking hot water with turmeric every morning cures "
        "diabetes completely within 3 weeks, doctors don't want you to know this!"
    )
    print(json.dumps(extract_claims(sample), indent=2))
