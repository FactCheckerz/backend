# Multimodal Medical Misinformation Detection & Fact Verification

## Colab (T4) vs. your M5 laptop — use both, for different jobs

**Build and demo on the M5 laptop. Only reach for Colab if you fine-tune.**

| | M5 laptop (10-core GPU, unified memory) | Colab T4 (16GB VRAM) |
|---|---|---|
| Running pretrained BGE embeddings + DeBERTa NLI + a 7B Ollama model | Comfortable — unified memory means no 8GB VRAM ceiling, MPS backend in PyTorch handles all these model sizes fine | Also fine, but you're sharing 16GB across embed model + reranker + NLI + LLM, and free-tier Colab disconnects your session — bad for a FastAPI server you want to keep alive during a demo |
| Fine-tuning DeBERTa-NLI on a custom labeled medical-misinformation set | Possible but slower — no CUDA kernels, no flash-attention, no bitsandbytes quantized training | Better — CUDA + mixed precision (fp16/bf16) training is meaningfully faster, and if your professor wants to see a "we trained something," T4 is the honest place to do it |
| Session persistence for a live demo | Yours, runs as long as you want | Free tier times out; you'd need Colab Pro or ngrok tunneling tricks |
| Network dependency (PubMed API, Ollama pulls) | Your own connection | Google's network, usually fine but adds a variable you don't control on demo day |

**Recommendation:** develop, index, and demo the whole pipeline locally on the
M5 (FastAPI + Gradio, both instructions below). If you want a genuine
training contribution beyond "I used pretrained SOTA models" — e.g.
fine-tuning the NLI cross-encoder or the reranker on a medical-claims dataset
(PUBHEALTH, SciFact, HealthVer are all public) — do *that specific step* in a
Colab T4 notebook, save the resulting weights, then load the fine-tuned
checkpoint back into `verification.py` on your laptop for the live pipeline.
This also gives you a legitimate "training vs inference infra" section in
your report, which reads well next to your professor's LSTM comment.

## Why this stack answers "why isn't this just LSTM from 2018"

- **Claim extraction**: instruction-tuned LLM (Qwen2.5/Llama3.2, 2024) doing
  structured JSON decomposition, not a BiLSTM-CRF tagger.
- **Retrieval**: BGE dense embeddings (2024 MTEB leaderboard model) fused with
  `bm25s` (a fast modern BM25 implementation), not TF-IDF/word2vec similarity.
- **Verification**: DeBERTa-v3 (disentangled attention, ELECTRA-style
  pretraining — architecturally newer and stronger than BERT/RoBERTa, not
  just "a bigger model"), used as a purpose-built NLI cross-encoder.
- **Explanation**: the same local LLM grounded via RAG on retrieved evidence,
  not a template-filling script.
- Every model above is 2023-2024 vintage and open-weight, so you can name
  every one of them by paper/release date if he pushes back.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# ffmpeg is required by both the audio/video pipeline (faster-whisper, yt-dlp) and video downloads
brew install ffmpeg            # macOS

# Local LLM runtime (used for claim extraction + explanation generation)
brew install ollama            # macOS
ollama serve &
ollama pull qwen2.5:7b-instruct   # or llama3.2:3b for a faster, smaller model

cp .env.example .env           # fill in ENTREZ_EMAIL (required by PubMed's API policy) and LLM_MODEL
```

## Run

```bash
# Terminal 1 — API
uvicorn main:app --port 8000
# docs at http://127.0.0.1:8000/docs
# (drop --reload, or pass --reload-dir . --reload-exclude '.venv/*' — plain --reload
#  also watches .venv and thrashes on every dependency file)

# Terminal 2 — UI
python app.py
```

## What's a stub vs. what's real

- **Real, working NLP/DL pipeline**: text cleaning → LLM claim extraction →
  PubMed evidence retrieval (hybrid dense+BM25) → cross-encoder reranking →
  DeBERTa NLI verification → rule-based decision fusion → LLM explanation.
- **Real, working multimodal input**: audio transcription (faster-whisper),
  video keyframe OCR (OpenCV + EasyOCR) fused with a transcript of the video's
  audio track, and downloads from any YouTube/Reel/TikTok/etc. link
  (`yt-dlp`) — see `preprocessing.py` and `media_fetch.py`. The Gradio UI
  (`app.py`) exposes these as separate "Upload video/audio" and "Reel /
  YouTube link" tabs alongside the text tab; the API exposes them via
  `POST /verify` (with a `url` field) and `POST /verify/upload` (multipart
  file upload).
- **Deliberately simple, not simplistic**: decision fusion is transparent
  rule-based aggregation over NLI votes rather than a second black-box
  classifier — see the docstring in `fusion.py` for why that's the right call
  given your likely dataset size.

## Extending for real accuracy work

1. Seed a proper evidence corpus beyond live PubMed calls: WHO fact sheets,
   Cochrane reviews, CDC pages — scrape once, cache as JSON, load via
   `index_documents()`.
2. Fine-tune `MoritzLaurer/deberta-v3-large-zeroshot-v2.0` on SciFact/HealthVer
   for medical-domain NLI (do this step on Colab T4, see table above).
3. Add calibration: log verdict vs. ground truth on a held-out claim set and
   plot a reliability diagram — this alone is a strong section for the report
   and costs almost no extra code.
