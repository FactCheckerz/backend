# Multimodal Medical Misinformation Detection & Fact Verification

A pipeline that takes a forwarded message — text, an uploaded audio/video
file, or a link to a Reel/YouTube video — extracts the medical claim(s) in
it, retrieves real biomedical evidence from PubMed, and produces a verdict
(True / False / Misleading / Unverified) with a plain-language, cited
explanation.

## Architecture

```
                         ┌─────────────────────────┐
                         │        INPUT             │
                         │  text / audio / video /   │
                         │  Reel-YouTube link         │
                         └────────────┬─────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │  Stage 1-2: Content        │
                         │  Processing (preprocessing.py) │
                         │  • text cleanup             │
                         │  • faster-whisper (audio→text)│
                         │  • OpenCV keyframes + EasyOCR │
                         │    (video overlay text)      │
                         │  • yt-dlp (link → local file) │
                         └────────────┬─────────────┘
                                      │  unified text
                         ┌────────────▼─────────────┐
                         │  Stage 3: Claim Extraction  │
                         │  (claim_extraction.py)      │
                         │  Local LLM (Ollama, Qwen2.5/ │
                         │  Llama3.2) → structured JSON │
                         │  claims, each normalized to  │
                         │  one checkable proposition   │
                         └────────────┬─────────────┘
                                      │  claim(s)
                    ┌─────────────────▼──────────────────┐
                    │  Stage 4: Evidence Retrieval          │
                    │  (evidence_resources.py + retrieval.py)│
                    │  • PubMed/Entrez pull for the claim's  │
                    │    topic, indexed into ChromaDB        │
                    │  • hybrid search: BGE dense embeddings │
                    │    + bm25s lexical, fused by weight    │
                    └─────────────────┬──────────────────┘
                                      │  candidate evidence
                         ┌────────────▼─────────────┐
                         │  Stage 5: Evidence Analysis │
                         │  (verification.py)          │
                         │  • bge-reranker-v2-m3 cross- │
                         │    encoder: relevance         │
                         │  • DeBERTa-v3 NLI cross-      │
                         │    encoder: entail/neutral/   │
                         │    contradict per evidence     │
                         └────────────┬─────────────┘
                                      │  scored, labeled evidence
                         ┌────────────▼─────────────┐
                         │  Stage 6-7: Decision Fusion  │
                         │  & Explanation (fusion.py)   │
                         │  • rule-based aggregation of  │
                         │    NLI votes → verdict +      │
                         │    confidence (transparent,   │
                         │    not a second black box)    │
                         │  • local LLM writes a cited,   │
                         │    plain-language explanation  │
                         └────────────┬─────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │        OUTPUT              │
                         │  verdict, confidence,       │
                         │  explanation, citations,     │
                         │  evidence detail             │
                         └───────────────────────────┘
```

## Project flow (request lifecycle)

1. **You submit input** — via the Gradio UI (`app.py`, three tabs: Text /
   Upload video-audio / Reel-YouTube link) or directly against the FastAPI
   backend (`main.py`).
2. **The UI calls the API** — `POST /verify` for text or a link (`url`
   field), `POST /verify/upload` for an uploaded file. The UI never touches
   the pipeline directly, so the API stays independently testable and
   swappable (e.g. a WhatsApp bot could hit the same endpoint later).
3. **`pipeline.py` orchestrates the rest**, in order:
   `preprocessing.unify_to_text` → `claim_extraction.extract_claims` →
   for each extracted claim: `evidence_resources.refresh_corpus_for_topic`
   (pulls fresh PubMed abstracts) → `retrieval.retrieve` (hybrid search) →
   `verification.analyze_claim` (rerank + NLI) → `fusion.full_output`
   (verdict + explanation).
4. **The API returns JSON**: one entry per extracted claim, each with
   `verdict`, `confidence`, `claim` (the exact proposition that was
   verified — this can differ from your raw input if the LLM rephrased it),
   `explanation`, `citations`, and `evidence_detail`.
5. **The Gradio UI renders it** as a verdict header, an AI-written
   explanation, and a list of evidence snippets labeled by NLI outcome.

### Files

| File | Role |
|---|---|
| `main.py` | FastAPI app — `/verify`, `/verify/upload`, `/health` |
| `app.py` | Gradio UI (Text / Upload / Link tabs) |
| `pipeline.py` | End-to-end orchestration |
| `preprocessing.py` | Text cleanup, audio transcription, video OCR |
| `media_fetch.py` | Downloads video/audio from a URL via `yt-dlp` |
| `claim_extraction.py` | LLM-based claim decomposition |
| `evidence_resources.py` | PubMed/Entrez fetch |
| `retrieval.py` | Hybrid dense + BM25 retrieval over ChromaDB |
| `verification.py` | Reranking + NLI entailment checking |
| `fusion.py` | Verdict aggregation + explanation generation |
| `config.py` | Central config (models, weights, `.env` loading) |

## Setup

You need: **Python 3.11+**, **ffmpeg**, and **Ollama** (for the local LLM).

### macOS

```bash
brew install ffmpeg ollama
ollama serve &
ollama pull qwen2.5:7b-instruct   # or: ollama pull llama3.2:3b for a faster, smaller model

cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env             # fill in ENTREZ_EMAIL (required by PubMed's API policy) and LLM_MODEL
```

### Windows

```powershell
# ffmpeg: download a build from https://www.gyan.dev/ffmpeg/builds/ and add its bin\ folder to PATH
# Ollama: download and run the installer from https://ollama.com/download/windows

ollama serve
# in a new terminal:
ollama pull qwen2.5:7b-instruct   # or: ollama pull llama3.2:3b for a faster, smaller model

cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env           # fill in ENTREZ_EMAIL (required by PubMed's API policy) and LLM_MODEL
```

> `ollama serve` occupies its terminal in the foreground — run the `ollama
> pull` and later commands in a separate terminal/tab with the same venv
> activated.

## Run

**macOS / Linux:**
```bash
# Terminal 1 — API
source .venv/bin/activate
uvicorn main:app --port 8000
# docs at http://127.0.0.1:8000/docs

# Terminal 2 — UI
source .venv/bin/activate
python app.py
```

**Windows:**
```powershell
# Terminal 1 — API
.venv\Scripts\activate
uvicorn main:app --port 8000

# Terminal 2 — UI
.venv\Scripts\activate
python app.py
```

Gradio prints a local URL (typically `http://127.0.0.1:7860`) — open that in
your browser.

If you want auto-reload on the API while editing (`--reload`), exclude
`.venv` from the file watcher or it'll thrash on every dependency file:
```bash
uvicorn main:app --reload --reload-dir . --reload-exclude '.venv/*' --port 8000
```

## Notes

- First run downloads several models (BGE embedder, reranker, DeBERTa NLI,
  EasyOCR, faster-whisper) — expect it to be slow the first time and fast
  after that.
- Decision fusion is deliberately transparent rule-based aggregation over
  NLI votes, not a second black-box classifier — see the docstring in
  `fusion.py` for the reasoning.
- To extend the evidence corpus beyond live PubMed calls (WHO fact sheets,
  Cochrane reviews, CDC pages), scrape once, cache as JSON, and load via
  `retrieval.index_documents()`.
