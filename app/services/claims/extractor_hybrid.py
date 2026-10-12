import json
import re
from typing import List
from groq import Groq
from app.core.claim_extraction_config import CLAIM_EXTRACTION_THRESHOLD
from app.schemas.claim_extraction import CandidateClaim
from app.services.claims.extractor_nlp import NLPClaimExtractor
from app.core.config import GROQ_API_KEY, GROQ_LLM


class HybridClaimExtractor:
    """
    Bart Identifies candidate factual spans
    Groq LLM refines candidates
    """

    def __init__(self):
        self.nlp_extractor = NLPClaimExtractor()
        self.client = Groq(api_key=GROQ_API_KEY)

    def _extract_json(self, content: str) -> list:
        """Extracts json array from LLM response"""
        content = content.strip()
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return parsed

        match = re.search(r"\[.*\]", content, re.DOTALL)
        if not match:
            return []
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return []
        return []

    def extract(self, text: str) -> List[CandidateClaim]:
        initial_candidates = self.nlp_extractor.extract(text)
        if not initial_candidates:
            return []
        candidate_text = "\n".join(
            f"{index+1}. {candidate.claim_text}"
            for index, candidate in enumerate(initial_candidates)
        )
        prompt = f"""
        You are a candidate claim extraction system for a fact-checking application.
        Your task is to review the candidate statements below.
        Keep a statement if it expresses an assertion that could potentially be checked against external evidence.
        Do NOT perform fact checking.
        Do NOT determine whether the statement is true or false.
        Do NOT add information that is not present in the candidate.
        Do NOT rewrite the statement into a canonical form.
        Remove candidates that are clearly:
        - questions
        - commands
        - greetings
        - pure opinions
        - subjective preferences
        - conversational filler
        - statements that cannot reasonably be verified
        Return ONLY a JSON array.
        Each item must have this structure:
        {{
            "claim_text": "candidate claim",
            "original_span": "original candidate text"
        }}
        Candidates:
        {candidate_text}"""
        response = self.client.chat.completions.create(
            model=GROQ_LLM,
            messages=[
                {
                    "role":"system",
                    "content":(
                        "You extract candidate claims for fact-checking pipeline. Return only valid JSON"
                    )
                },
                {
                    "role":"user",
                    "content":prompt
                }
            ],
            temperature=0
        )
        content = response.choices[0].message.content or ""
        refined = self._extract_json(content)
        results = []
        for item in refined:
            if not isinstance(item,dict):
                continue
            claim_text = str(item.get("claim_text","")).strip()
            original_span = str(item.get("original_span","")).strip()
            if not claim_text:
                continue
            if not original_span:
                original_span = claim_text
            results.append(
                CandidateClaim(claim_text=claim_text,original_span=original_span)
            )
        return results