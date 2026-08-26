"""
Central config. Nothing here is a secret — put real API keys in a .env file
and load them with python-dotenv (already in requirements.txt).
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ---- Embedding model (dense retrieval) ----
# BGE (BAAI General Embedding) large-en-v1.5 — 2024 model, currently one of the
# strongest open English embedding models on the MTEB leaderboard, beats the
# old sentence-BERT (all-MiniLM / paraphrase-*) family by a wide margin on
# retrieval tasks, which is exactly what "Evidence Retrieval" needs.
EMBED_MODEL = "BAAI/bge-large-en-v1.5"

# ---- Cross-encoder for NLI / entailment ----
# DeBERTa-v3-large fine-tuned for NLI + zero-shot (MoritzLaurer, 2024 checkpoint).
# DeBERTa-v3 already beats BERT/RoBERTa on GLUE/MNLI at the same size because of
# disentangled attention + ELECTRA-style pretraining — this is a genuinely
# stronger architecture, not just a newer label.
NLI_MODEL = "MoritzLaurer/deberta-v3-large-zeroshot-v2.0"

# ---- Cross-encoder for evidence re-ranking ----
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"  # 2024, multilingual, strong on medical/scientific text

# ---- Local generative LLM for claim decomposition + explanations ----
# Runs through Ollama so the SAME code works on your M5 laptop (MLX-accelerated
# Ollama build) and on Colab (Ollama installed via apt, GPU disabled — or swap
# to a HF pipeline there, see notes in claim_extraction.py).
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b-instruct")  # or "llama3.2:3b" for speed

# ---- Vector store ----
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_store")
COLLECTION_NAME = "medical_evidence"

# ---- PubMed / Entrez ----
ENTREZ_EMAIL = os.getenv("ENTREZ_EMAIL", "your_email@example.com")
ENTREZ_API_KEY = os.getenv("ENTREZ_API_KEY", "")  # optional, raises rate limit 3->10 req/s

# ---- Retrieval fusion weights ----
DENSE_WEIGHT = 0.6
BM25_WEIGHT = 0.4
TOP_K_RETRIEVE = 15
TOP_K_AFTER_RERANK = 5

# ---- Device ----
# "mps" on the M5 laptop (Apple Silicon), "cuda" on Colab T4, "cpu" as fallback.
import torch
if torch.backends.mps.is_available():
    DEVICE = "mps"
elif torch.cuda.is_available():
    DEVICE = "cuda"
else:
    DEVICE = "cpu"
