from typing import List
from functools import lru_cache
from transformers import pipeline
from app.core.claim_extraction_config import CLAIM_EXTRACTION_THRESHOLD
from app.schemas.claim_extraction import CandidateClaim



@lru_cache(maxsize=1)
def get_bart_classifier():
    return pipeline(
        "zero-shot-classification",
        model = "facebook/bart-large-mnli"
    )

class NLPClaimExtractor:
    """Uses BART-MNLI to identify sentences/spans that appear 
    to contain factual assertions
    This produces candidate claims only."""

    def _split_into_sentences(self,text: str) -> List[str]:
        """Basic sentence segmentation"""
        text = text.strip()
        if not text:
            return []
        sentences = []
        current = ""
        for char in text:
            current+=char
            if char in ".!?":
                cleaned = current.strip()
                if cleaned:
                    sentences.append(cleaned)
                current=""
        if current.strip():
            sentences.append(current.strip())
        return sentences

    def extract(self,text: str) -> List[CandidateClaim]:
        sentences = self._split_into_sentences(text)
        if not sentences:
            return []
        classifier = get_bart_classifier()
        candidates = []
        labels = [
            "a factual statement",
            "an opinion, question, command, or non-factual statement"
        ]
        for sentence in sentences:
            if len(sentence.strip())<5:
                continue
            result = classifier(
                sentence,
                candidate_labels = labels,
                multi_label = False
            )
            top_label = result["labels"][0]
            confidence = float(result["scores"][0])
            if(top_label==labels[0] and confidence>=CLAIM_EXTRACTION_THRESHOLD):
                candidates.append(
                    CandidateClaim(
                        claim_text = sentence.strip(),
                        original_span = sentence.strip(),
                        confidence = confidence
                    )
                )
        return candidates