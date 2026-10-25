# Multimodal Medical Misinformation Detection & Fact Verification

A pipeline that takes a forwarded message — text, an uploaded audio/video
file, or a link to a Reel/YouTube video — extracts the medical claim(s) in
it, retrieves real biomedical evidence from PubMed, and produces a verdict
(**True**, **False**, **Misleading / Partially True**, or **Unverified**) with a plain-language, cited
explanation.

Everything except the PubMed lookup can run locally: the LLM through Ollama,
and the speech, OCR, embedding, reranking and NLI models through
PyTorch / CTranslate2. Optionally, you can use Groq's hosted Whisper for
much more accurate speech-to-text (see
[Speech-to-text](#speech-to-text-groq-or-local)).

---

## Quick start

If you already have Python, ffmpeg and Ollama installed:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # then set ENTREZ_EMAIL
ollama pull qwen2.5:7b-instruct

# Terminal 1
ollama serve
# Terminal 2
uvicorn main:app --port 8000
# Terminal 3
python app.py                        # open http://127.0.0.1:7860
```

Otherwise follow the full steps below.

---

## 1. Prerequisites

| Tool | Why it's needed | Check it's installed |
|---|---|---|
| **Python 3.11+** (developed on 3.14) | Runs the backend | `python3 --version` |
| **ffmpeg** | Decodes audio/video for Whisper and merges `yt-dlp` downloads | `ffmpeg -version` |
| **Ollama** | Serves the local LLM used for claim extraction and explanations | `ollama --version` |
| **~10 GB free disk** | Model weights (LLM ≈ 4.7 GB, plus embedder, reranker, NLI, OCR, Whisper) | — |
| **16 GB RAM recommended** | All models are loaded in the same process. With 8 GB, use `llama3.2:3b` | — |

### macOS

```bash
brew install python ffmpeg ollama
```

### Windows

- **Python:** install from <https://www.python.org/downloads/> and tick *"Add python.exe to PATH"*.
- **ffmpeg:** download a build from <https://www.gyan.dev/ffmpeg/builds/>, unzip it, and add its `bin\` folder to your `PATH`.
- **Ollama:** run the installer from <https://ollama.com/download/windows>.

### Linux (Debian/Ubuntu)

```bash
sudo apt install python3 python3-venv ffmpeg
curl -fsSL https://ollama.com/install.sh | sh
```

---

## 2. Install

All commands are run from the `backend/` folder.

**macOS / Linux**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Windows (PowerShell)**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> If PowerShell refuses to run `activate`, run
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again.

---

## 3. Configure

Copy the example env file and fill it in:

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `ENTREZ_EMAIL` | **Yes** | `your_email@example.com` | Your email. NCBI requires one for PubMed API calls |
| `ENTREZ_API_KEY` | No | empty | Raises the PubMed rate limit from 3 to 10 requests/sec. Create one under [NCBI account settings](https://www.ncbi.nlm.nih.gov/account/settings/) |
| `LLM_MODEL` | No | `qwen2.5:7b-instruct` | Any model you have pulled in Ollama |
| `GROQ_API_KEY` | No | empty | Turns on Groq-hosted Whisper for audio/video. Get a free key at [console.groq.com/keys](https://console.groq.com/keys) |
| `GROQ_WHISPER_MODEL` | No | `whisper-large-v3-turbo` | `whisper-large-v3` is slightly more accurate but slower |
| `LOCAL_WHISPER_MODEL` | No | `base` | Local faster-whisper model used when Groq isn't available: `tiny` / `base` / `small` / `medium` / `large-v3-turbo` |
| `CHROMA_DIR` | No | `./chroma_store` | Where the evidence vector index is stored |

Model names, retrieval weights and top-k values live in [config.py](config.py).

### Speech-to-text: Groq or local

Audio and video are transcribed in one of two ways:

1. **Groq** (used when `GROQ_API_KEY` is set). ffmpeg strips the audio into a
   small mono mp3, which is sent to Groq's `whisper-large-v3-turbo`. This is
   much more accurate on medical terms and accented speech, and takes a few
   seconds. It needs internet access, and the audio leaves your machine.
2. **Local faster-whisper** (used when there's no key, or when the Groq call
   fails because you're offline, hit a rate limit, or the file is over 25 MB).
   It runs fully offline. On a Mac it runs on CPU, so it's slower, and the
   default `base` model is less accurate.

The API terminal shows which backend ran and logs a message when it falls
back to local.

---

## 4. Pull the LLM

Start Ollama, then pull a model in a second terminal:

```bash
ollama serve                       # leave this running
```

```bash
ollama pull qwen2.5:7b-instruct    # recommended (≈4.7 GB)
# or, on low-RAM machines:
ollama pull llama3.2:3b            # then set LLM_MODEL=llama3.2:3b in .env
```

> On macOS, if you installed the Ollama desktop app it already runs in the
> background, so you can skip `ollama serve`. If you get
> `address already in use`, Ollama is already running.

---

## 5. Run

You need **three things running**: Ollama, the API, and the UI. Use a
separate terminal for each, and activate the venv in the API and UI terminals.

| Terminal | macOS / Linux | Windows |
|---|---|---|
| 1. LLM server | `ollama serve` | `ollama serve` |
| 2. API (port 8000) | `source .venv/bin/activate`<br>`uvicorn main:app --port 8000` | `.venv\Scripts\activate`<br>`uvicorn main:app --port 8000` |
| 3. UI (port 7860) | `source .venv/bin/activate`<br>`python app.py` | `.venv\Scripts\activate`<br>`python app.py` |

Then open **<http://127.0.0.1:7860>** in your browser.

The UI has three tabs:

- **Text**: paste a forwarded message.
- **Upload video/audio**: upload a file and pick its media type.
- **Reel / YouTube link**: paste any link `yt-dlp` supports (YouTube,
  Instagram Reels, TikTok, …).

Progress for every stage is logged in the **API terminal**, so watch it if a
request seems slow.

> **The first request is slow.** On first use the pipeline downloads the
> BGE embedder, BGE reranker, DeBERTa NLI model, EasyOCR weights and the
> Whisper model (a few GB in total, cached under `~/.cache/huggingface`).
> Later requests skip this step.

### Auto-reload while developing

```bash
uvicorn main:app --reload --reload-dir . --reload-exclude '.venv/*' --port 8000
```

Excluding `.venv` matters. Without it the watcher restarts the server on
every file change inside the installed packages.

---

## 6. Using the API directly

Interactive docs (Swagger) are at **<http://127.0.0.1:8000/docs>**.

| Method | Endpoint | Body | Use for |
|---|---|---|---|
| `GET` | `/health` | — | Check the API is up |
| `POST` | `/verify` | JSON `{"text": "...", "input_type": "text"}` | Plain text |
| `POST` | `/verify` | JSON `{"url": "...", "input_type": "video" \| "audio"}` | A Reel / YouTube link |
| `POST` | `/verify/upload` | multipart: `file`, `input_type` | Uploaded audio/video |

```bash
# Health check
curl http://127.0.0.1:8000/health

# Text
curl -X POST http://127.0.0.1:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"text": "Drinking hot water with lemon cures COVID-19", "input_type": "text"}'

# Link
curl -X POST http://127.0.0.1:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/shorts/XXXXXXXX", "input_type": "video"}'

# File upload
curl -X POST http://127.0.0.1:8000/verify/upload \
  -F "file=@sample.mp4" -F "input_type=video"
```

Example response (one entry per extracted claim):

```json
{
  "claims": [
    {
      "claim": "Drinking hot water with lemon cures COVID-19.",
      "verdict": "False",
      "confidence": 0.82,
      "evidence_strength": 1.37,
      "supporting_count": 0,
      "contradicting_count": 3,
      "explanation": "No clinical evidence shows ...",
      "citations": [
        { "source": "PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/" }
      ],
      "evidence_detail": [
        {
          "source": "PubMed",
          "text": "...",
          "relevance_score": 0.91,
          "nli_label": "contradiction",
          "nli_confidence": 0.88
        }
      ],
      "medical_entities": ["lemon", "COVID-19"]
    }
  ]
}
```

`claim` is the proposition that was actually verified. It can differ from
your raw input because the LLM normalises it into one checkable sentence.

---

## Architecture

```
 INPUT: text / audio / video / Reel-YouTube link
   │
   ▼
 Stage 1-2  Content processing           preprocessing.py, media_fetch.py
            • text cleanup (forward headers, emoji, URLs)
            • yt-dlp: link → local mp4
            • Whisper: audio → transcript
              (Groq whisper-large-v3-turbo, falls back to local faster-whisper)
            • OpenCV keyframes + EasyOCR: on-screen text
   │  unified text
   ▼
 Stage 3    Claim extraction             claim_extraction.py
            • local LLM (Ollama: Qwen2.5 / Llama3.2) → JSON list of
              normalised, independently checkable claims
   │  claim(s)
   ▼
 Stage 4    Evidence retrieval           evidence_resources.py, retrieval.py
            • fresh PubMed abstracts for the claim, indexed into ChromaDB
            • hybrid search: BGE dense (0.6) + BM25 lexical (0.4)
   │  top-15 candidates
   ▼
 Stage 5    Evidence analysis            verification.py
            • bge-reranker-v2-m3 cross-encoder → top-5 by relevance
            • DeBERTa-v3 NLI → entail / neutral / contradict per snippet
   │  scored, labelled evidence
   ▼
 Stage 6-7  Decision fusion & explanation   fusion.py
            • transparent rule-based aggregation of NLI votes →
              verdict + confidence
            • local LLM writes a cited, plain-language explanation
   │
   ▼
 OUTPUT: verdict, confidence, explanation, citations, evidence detail
```

### Request lifecycle

1. The Gradio UI ([app.py](app.py)) sends the input to the FastAPI backend
   ([main.py](main.py)) over HTTP. It never imports the pipeline directly,
   so the API can be tested on its own and reused by other clients, such as
   a WhatsApp bot.
2. [pipeline.py](pipeline.py) runs `unify_to_text` → `extract_claims` →
   then, for each claim, `refresh_corpus_for_topic` → `retrieve` →
   `analyze_claim` → `full_output`.
3. The API returns JSON, and the UI renders a verdict header, the
   explanation, and the evidence list labelled with each NLI outcome.

### Files

| File | Role |
|---|---|
| [main.py](main.py) | FastAPI app: `/verify`, `/verify/upload`, `/health` |
| [app.py](app.py) | Gradio UI (Text / Upload / Link tabs) |
| [pipeline.py](pipeline.py) | End-to-end orchestration |
| [preprocessing.py](preprocessing.py) | Text cleanup, Whisper transcription, video OCR |
| [media_fetch.py](media_fetch.py) | Downloads media from a URL via `yt-dlp` |
| [claim_extraction.py](claim_extraction.py) | LLM-based claim decomposition |
| [evidence_resources.py](evidence_resources.py) | PubMed / Entrez fetch |
| [retrieval.py](retrieval.py) | Hybrid dense + BM25 retrieval over ChromaDB |
| [verification.py](verification.py) | Reranking + NLI entailment |
| [fusion.py](fusion.py) | Verdict aggregation + explanation generation |
| [progress.py](progress.py) | Timestamped stage logging to the terminal |
| [config.py](config.py) | Central config (models, weights, device, `.env` loading) |

**Device selection:** models run on `mps` (Apple Silicon), `cuda` (NVIDIA)
or `cpu`, chosen automatically in `config.py`. faster-whisper has no MPS
backend, so it falls back to CPU (int8) on Macs.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `httpx.ConnectError` in the UI | The API isn't running. Start `uvicorn main:app --port 8000` first |
| `ollama._types.ResponseError: model not found` | Run `ollama pull <LLM_MODEL>` and check that the name in `.env` matches `ollama list` |
| `Connection refused` on port 11434 | Ollama isn't running. Run `ollama serve` |
| `ffmpeg not found` / audio errors | Install ffmpeg and make sure it's on your `PATH` |
| Link input fails with an HTTP 403 or "Sign in to confirm" | Update the downloader with `pip install -U yt-dlp`. Some Instagram/YouTube content needs login cookies |
| Every claim comes back **Unverified** | PubMed returned nothing usable. Check `ENTREZ_EMAIL` is set and you're online, then try a more specific claim |
| Log shows `Groq transcription failed (401 ...)` | `GROQ_API_KEY` is wrong or expired. Generate a new key |
| Log shows `Groq transcription failed (429 ...)` | You hit Groq's free-tier rate limit. It falls back to local automatically, or you can wait a minute |
| Transcripts are poor without Groq | Set `LOCAL_WHISPER_MODEL=small` or `large-v3-turbo`. It's more accurate but slower on CPU |
| Out-of-memory / machine freezes | Switch to `LLM_MODEL=llama3.2:3b` and close other heavy apps |
| Want a clean evidence index | Stop the API and delete the `chroma_store/` folder. It's rebuilt on the next request |

---

## Notes

- Decision fusion is deliberately rule-based aggregation over NLI votes, not
  a second black-box classifier, so every verdict can be traced to the
  evidence that produced it. See the docstring in [fusion.py](fusion.py).
- To go beyond live PubMed calls (WHO fact sheets, Cochrane reviews, CDC
  pages), scrape the sources once, cache them as JSON, and load them with
  `retrieval.index_documents()`.
- This is a research prototype and **not medical advice**.
