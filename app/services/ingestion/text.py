from app.services.ingestion.exceptions import InvalidInputError
from app.services.ingestion.hashing import calculate_text_hash

def normalize_text(text: str) -> str:
    """Normalize user provided text while keeping actual meaning/content"""
    if not text:
        raise InvalidInputError(
            "Text input cannot be empty"
        )
    normalized = " ".join(text.split())
    if not normalized:
        raise InvalidInputError(
            "Text input cannot be empty"
        )
    return normalized

def ingest_text(text: str) -> dict:
    """Normalize text and calculate its SHA-256 hash"""
    normalized_text = normalize_text(text)
    text_hash = calculate_text_hash(normalized_text)
    return {
        "input_type":"text",
        "raw_text":normalized_text,
        "text_hash":text_hash
    }