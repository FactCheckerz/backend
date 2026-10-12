from typing import List
from app.core.claim_extraction_config import CLAIM_EXTRACTION_STRATEGY
from app.schemas.claim_extraction import CandidateClaim
from app.services.claims.extractor_nlp import NLPClaimExtractor
from app.services.claims.extractor_hybrid import HybridClaimExtractor

class ClaimExtractionService:
    def __init__(self):
        if CLAIM_EXTRACTION_STRATEGY == "nlp":
            self.extractor = NLPClaimExtractor()
        elif CLAIM_EXTRACTION_STRATEGY == "hybrid":
            self.extractor = HybridClaimExtractor()
        else:
            raise ValueError(f"Unsupported claim extraction strategy")

    def extract(self,text: str)->List[CandidateClaim]:
        if not text or not text.strip():
            return []
        return self.extractor.extract(text)