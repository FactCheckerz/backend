import os

CLAIM_EXTRACTION_STRATEGY = os.getenv(
    "CLAIM_EXTRACTION_STRATEGY",
    "nlp"
).lower()

if CLAIM_EXTRACTION_STRATEGY not in {"nlp","hybrid"}:
    raise ValueError("Caim extraction strategy must be either nlp or hybrid")

# bart confidence thershold for candidate claims extraction
CLAIM_EXTRACTION_THRESHOLD = float(os.getenv("CLAIM_EXTRACTION_THRESHOLD","0.65"))
