# FACTCHECKER — Project Context & Specification

> This file is the single source of truth for the project. Paste this file back
> into a new conversation whenever context needs to be restored, together with
> `logs.md` (which tracks what has actually been built so far).

---

## 1. Problem Statement

Short-form content (Instagram Reels, YouTube Shorts, Facebook Shorts), forwarded
audio (e.g. WhatsApp voice notes), and plain text messages are a major vector for
misinformation. FACTCHECKER lets a user submit a piece of content and get back:

- The list of factual **claims** made in that content
- For each claim, a **verdict** (Supported / Not Supported / Cannot Say)
- A **confidence score** per verdict
- **Evidence & sources** backing the verdict
- A plain-language **explanation**

The academic scope (NLP coursework) is narrowed to **one applied domain: Medical
claims**. The product itself is built with two switchable modes so the same
pipeline generalizes beyond the course requirement.

---

## 2. Modes

A single UI toggle (e.g. a segmented control in the header) switches the active
pipeline configuration. The toggle is a **request-time parameter**, not a
separate app.

| Mode | Behavior |
|---|---|
| **General** | Claim detection + verification tuned for broad topics. Evidence retrieval hits general web/news sources. |
| **Medical** | Claim detection prompt/model is tuned to surface health/medical claims specifically. Evidence retrieval is restricted/prioritized to trusted medical sources (e.g. PubMed, WHO, CDC, Cochrane, FDA, peer-reviewed journals). Verification agent uses a stricter confidence threshold and requires higher-quality evidence before marking something "Supported" — false negatives ("cannot say") are preferred over confident false positives, given the real-world stakes of medical misinformation. |

Mode is passed through the entire pipeline (ingestion → claim detection →
verification agent) and stored alongside the result in Supabase so cached
results are mode-specific (a claim's verdict in Medical mode is cached
separately from General mode).

---

## 3. End-to-End User Flow

(Derived from the attached workflow diagram, formalized.)

1. User opens the web app.
2. User selects **input type**: `Text` / `Audio` / `Video`.
   - **Video** → either paste a URL (YT Shorts / Insta Reels / FB Shorts) or
     upload an `.mp4` file (client + server side file-size validation).
   - **Audio** → upload `.mp3` (or common audio formats).
   - **Text** → paste/type text directly (a message, transcript, article snippet, etc).
3. User selects **mode**: General / Medical.
4. Backend ingests input:
   - URL → downloader extracts video, extracts audio track.
   - Uploaded video → extract audio track.
   - Audio → passed to Speech-to-Text (ASR).
   - Text → passed through unchanged.
   - Result of this stage: **normalized text / transcript**.
5. **Claim Detection** (pure NLP, no agent): the normalized text is run through
   a claim-detection model/pipeline to produce a **list of discrete claims**,
   each with the source span (character offsets / sentence index) it came from.
6. **Claim Review UI**: the list of detected claims is shown to the user.
   - User can **deselect/remove** claims that shouldn't be checked (e.g. jokes,
     opinions mistakenly flagged).
   - The **original full list is always retained**; removed claims can be
     restored at any time before submission (a simple checked/unchecked list,
     not a destructive delete).
   - User confirms the final claim set to proceed.
7. **Claim Processing**: confirmed claims are restructured/normalized into a
   canonical, self-contained statement each (resolving pronouns, adding
   implicit context) so they can be independently verified out of context.
8. **Agentic Verification** (LangGraph): for each processed claim, an agent
   graph:
   - Retrieves evidence (search/retrieval tools, mode-aware source selection).
   - Compares the claim against retrieved evidence.
   - Produces a verdict: `Supported` / `Not Supported` / `Cannot Say`.
   - Produces a confidence score.
   - Produces an explanation + list of sources/evidence snippets.
9. **Final Result** is assembled and returned:
   - Full claim list
   - Per-claim: verdict, confidence score, explanation, evidence & sources
10. Result (and the raw input hash/URL) is **persisted in Supabase**. If the
    same URL or the same audio/video (by content hash) is submitted again by
    any user, the cached result is served immediately — no re-processing.

---

## 4. Architecture

```
┌───────────────────┐        ┌────────────────────────┐        ┌────────────────┐
│     Next.js FE     │  REST  │     FastAPI Backend      │        │    Supabase     │
│    (App Router)     │◄──────►│  (modular services,       │◄──────►│  Postgres only  │
│  Tailwind + shadcn   │  /api  │   rate-limited endpoints)  │        │ (cache table,   │
└───────────────────┘        │                            │        │  no user data,  │
                               │  ┌──────────────────────┐  │        │  no auth)       │
                               │  │ Ingestion Service       │  │        └────────────────┘
                               │  ├──────────────────────┤  │
                               │  │ ASR Service              │  │
                               │  ├──────────────────────┤  │
                               │  │ Claim Detection          │  │
                               │  │ (NLP, classic)           │  │
                               │  ├──────────────────────┤  │
                               │  │ Claim Processing         │  │
                               │  ├──────────────────────┤  │
                               │  │ LangGraph                │  │
                               │  │ Verification Agent       │  │
                               │  └──────────────────────┘  │
                               └────────────────────────┘
```

### 4.1 Frontend — Next.js
- Next.js (App Router) + TypeScript.
- Tailwind CSS + a component library (shadcn/ui) for a modern, professional look.
- Fully responsive: mobile, tablet, laptop, desktop breakpoints.
- Pages/flows:
  - Landing / input page (mode toggle + input-type tabs)
  - Claim review page (editable claim checklist)
  - Results page (per-claim verdict cards: verdict badge, confidence meter,
    explanation, expandable sources list)
  - (Optional, later) A "recently checked" feed pulled from the shared cache
    table — since nothing is user-attributed, this would show everyone the
    same global list. Not a Phase 1 concern.
- Calls backend via plain REST requests — no auth token/header involved, since
  there's no login system (see §8).

### 4.2 Backend — FastAPI
- Modular, layered structure (routers → services → agents/pipelines → db).
- Async endpoints throughout (I/O bound: downloads, ASR calls, LLM calls,
  retrieval calls) to keep processing fast and support concurrent requests.
- Background/streaming pattern for long-running jobs (see §7 — job/status model)
  so the frontend isn't stuck on one blocking HTTP call for a multi-minute
  video-processing pipeline.
- Route protection is rate-limiting only (see §8) — no auth dependency, no
  login-gated routes.

### 4.3 Data — Supabase
- Postgres used **purely as a cache/lookup store**, not as user data storage.
- **No user data is stored, ever, and there is no auth system at all.** The
  `submissions` table has no `user_id` and no link back to who submitted
  something — the app has no concept of a logged-in user.
- What *is* stored per submission (all needed only to detect "have we seen
  this content before?" and to serve the cached result):
  - the input URL (for link-based video), **or**
  - the raw text (for text input) plus a hash of it for fast lookup, **or**
  - a content hash of the uploaded audio/video (the file itself is never
    stored — it's hashed, processed, then discarded)
  - the final result (claims, verdicts, confidence, evidence)
- Because there's no user linkage, there's no per-user RLS isolation to
  design — the whole table is a shared cache. Row-level security can still be
  turned on with a simple rule (e.g. only the backend's service role may
  read/write), since there's no "my data vs your data" split to enforce.
- Supabase Storage is **not used** — media is streamed through the backend,
  hashed, processed, and discarded; nothing binary is persisted.

---

## 5. Database Schema (Supabase / Postgres) — draft, finalized in Phase 1

```sql
-- one row per unique piece of source content ever submitted (cache table — no user linkage)
create table submissions (
  id uuid primary key default gen_random_uuid(),
  input_type text not null check (input_type in ('text','audio','video_url','video_file')),
  mode text not null check (mode in ('general','medical')),
  raw_url text,                 -- populated for video_url inputs (yt shorts / insta reels / fb shorts)
  content_hash text,            -- populated for audio/video_file inputs (sha256 of the media, file itself NOT stored)
  raw_text text,                -- populated for text inputs (kept, since text isn't sensitive binary media)
  text_hash text,               -- sha256 of raw_text, for fast/indexed lookup on text inputs
  status text not null default 'pending', -- pending | processing | claims_ready | verifying | done | failed
  created_at timestamptz default now()
);

-- uniqueness for cache hits — exactly one of these three applies per row, matching input_type
create unique index submissions_url_mode_uidx on submissions (raw_url, mode) where raw_url is not null;
create unique index submissions_hash_mode_uidx on submissions (content_hash, mode) where content_hash is not null;
create unique index submissions_texthash_mode_uidx on submissions (text_hash, mode) where text_hash is not null;

create table claims (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid references submissions(id) on delete cascade,
  claim_text text not null,           -- processed/canonical claim
  original_span text,                 -- original excerpt the claim came from
  included boolean default true,      -- user's include/exclude choice
  verdict text,                       -- supported | not_supported | cant_say
  confidence numeric,                 -- 0.0 - 1.0
  explanation text,
  evidence jsonb,                     -- [{source, url, snippet}, ...]
  created_at timestamptz default now()
);
```

Notes:
- Caching is keyed on **(raw_url, mode)** or **(content_hash, mode)** — same
  URL, different mode (General vs Medical), is treated as a different
  verification run since evidence sourcing differs.
- `content_hash` = SHA-256 of the uploaded media bytes (or of the extracted
  audio track — decide in Phase 1 whether we hash the raw file or the decoded
  audio to be resilient to re-encoding).

---

## 6. The Agentic Layer (LangGraph)

Only the **verification stage** is agentic. Ingestion → transcription → claim
detection is a deterministic NLP pipeline (fast, cheap, predictable).

For each confirmed/processed claim, a LangGraph graph runs:

```
        ┌───────────────┐
        │ start(claim)   │
        └──────┬────────┘
               ▼
        ┌───────────────┐
        │ plan_retrieval │  (decide search queries, mode-aware source scope)
        └──────┬────────┘
               ▼
        ┌───────────────┐
        │ retrieve_evidence │ (web search / medical DB / vector store tools)
        └──────┬────────┘
               ▼
        ┌───────────────┐
        │ assess_evidence │ (enough evidence? relevant? conflicting?)
        └──────┬────────┘
          not enough │ enough
        ◄────────────┘        │
   (loop back to retrieval,   ▼
    bounded retries)   ┌───────────────┐
                        │ verify_claim   │ (compare claim vs evidence → verdict)
                        └──────┬────────┘
                               ▼
                        ┌───────────────┐
                        │ score_confidence│
                        └──────┬────────┘
                               ▼
                        ┌───────────────┐
                        │ explain + cite │
                        └───────────────┘
```

- Graph state includes: claim text, mode, retrieved evidence accumulator,
  retry count, final verdict object.
- Claims are verified **concurrently** (fan-out across claims, each running its
  own graph instance) to keep total latency down — this is the main "fast
  processing" lever for the verification stage.
- Medical mode restricts/prioritizes the retrieval tool's source list and
  raises the evidence-sufficiency bar in `assess_evidence`.

---

## 7. Processing Model (Fast Processing / UX under load)

Video/audio pipelines are not instant (download + ASR can take real time), so:
- Submission endpoint returns immediately with a `submission_id` and
  `status: pending`.
- Backend processes asynchronously (FastAPI `BackgroundTasks` initially;
  can graduate to a proper queue — e.g. Celery/RQ/Arq with Redis — if load
  requires it later).
- Frontend polls (or subscribes via Supabase Realtime on the `submissions`
  row) for status transitions: `pending → processing → claims_ready →
  verifying → done`.
- The **claim list is delivered to the user as soon as it's ready** (before
  verification starts) so the user can edit claims while the UI is already
  responsive — verification only starts once the user confirms the claim set.
- Cache hits (matching `raw_url`+`mode` or `content_hash`+`mode`) short-circuit
  straight to `done` with the stored result.

---

## 8. Route Protection (Rate Limiting Only — No Auth Layer)

There is **no authentication/login system in this app at all** — no signup,
no login, no sessions, no Supabase Auth. The app is open to anyone who visits
it. The only protection needed is against **abuse/DDoS-style hammering** of
the processing endpoints (which are the expensive ones: download, ASR, LLM
calls, retrieval).

- **Rate limiting** is applied at the FastAPI layer on the submission/
  processing endpoints (e.g. per-IP, sliding window — exact limits tuned once
  we see real usage/costs; something like N requests per minute per IP as a
  starting point).
- Implementation: a lightweight middleware/dependency (e.g. `slowapi`, or a
  simple Redis-backed counter if Redis is already in play for background
  jobs) — no external auth provider needed.
- Cheap/static endpoints (`/health`, etc.) are excluded from rate limiting;
  the limit targets the ingestion/processing/verification endpoints
  specifically.
- Since there's no login, rate limiting is necessarily IP-based (with
  awareness that this is imperfect behind shared IPs/proxies — acceptable
  tradeoff for a coursework-scope project; can be revisited later with e.g.
  a lightweight per-browser token or CAPTCHA on abuse spikes if needed).
- This section replaces any earlier notion of an auth layer — there is
  nothing to log into, and no user identity anywhere in the system (consistent
  with §4.3 — no user data is ever stored).

---

## 9. Non-Functional Requirements

- **Fast processing**: async I/O throughout, concurrent claim verification,
  URL/hash-based caching, early delivery of claim list before verification.
- **Modern, professional, responsive UI**: Tailwind + shadcn/ui, mobile/tablet/
  laptop/desktop breakpoints, loading/skeleton states for every async step.
- **Security**: rate limiting on submission/processing endpoints to guard
  against DDoS/abuse, plus input validation (file size/type limits on
  uploads). No auth system, no user data anywhere in the app.
- **Extensibility**: mode system designed so a 3rd/4th domain-specific mode
  (e.g. Finance, Politics) could be added later without restructuring the
  pipeline — only the claim-detection prompt and evidence-source config differ
  per mode.

---

## 10. Tech Stack Summary

| Layer | Choice |
|---|---|
| Frontend framework | Next.js (App Router, TypeScript) |
| Styling | Tailwind CSS + shadcn/ui |
| Backend framework | Python + FastAPI (async) |
| Claim detection (NLP) | classic NLP/ML pipeline — model choice finalized in Phase 1 |
| ASR (speech-to-text) | to be finalized in Phase 1 (e.g. Whisper) |
| Video/URL downloading | yt-dlp (supports YT Shorts, Insta Reels, FB Shorts) |
| Agent orchestration | LangGraph |
| LLM provider | to be finalized (Anthropic API assumed by default) |
| Database | Supabase Postgres — cache table only, no Auth, no Storage |
| Rate limiting | `slowapi` (or Redis-backed counter) on processing endpoints |
| Caching key | URL or content-hash (SHA-256), scoped per mode |
| Background jobs | FastAPI BackgroundTasks → (future) Celery/Arq + Redis if needed |

---

## 11. Project Phases

Implementation proceeds backend-first, in modular, independently testable
phases. After each phase is implemented and confirmed working, `logs.md` gets
a new dated entry summarizing what was built, key decisions made, and any open
TODOs — so context can be restored in a fresh conversation by pasting both
files back in.

- **Phase 1 — Ingestion → Claim Detection (backend core, no agent/rate-limiting yet)**
  Input handling for URL / mp4 upload / mp3 upload / text; URL/video
  downloading (yt-dlp); audio extraction; ASR transcription; claim detection
  NLP pipeline; Supabase schema creation; URL/hash-based cache lookup;
  returns a claim list via API. This is today's target.

- **Phase 2 — Claim Review & Editing**
  API + logic for include/exclude claim state, restore-to-original, and
  "confirm claim set" endpoint that hands off to processing.

- **Phase 3 — Claim Processing (canonicalization)**
  Restructuring confirmed claims into self-contained, checkable statements.

- **Phase 4 — Agentic Verification (LangGraph)**
  Build the retrieval → assess → verify → score → explain graph; concurrent
  fan-out per claim; mode-aware behavior (General vs Medical sourcing rules).

- **Phase 5 — Result Aggregation & Persistence**
  Assemble final structured result; write claims + verdicts to Supabase;
  status-tracking model (`pending/processing/claims_ready/verifying/done`).

- **Phase 6 — Route Protection (Rate Limiting)**
  Add rate-limiting middleware/dependency to the ingestion/processing/
  verification endpoints to guard against DDoS/abuse. No auth system.

- **Phase 7 — Frontend Build-Out**
  Next.js app: input page, mode toggle, claim review UI, results UI,
  responsive design pass, loading/status states wired to backend polling/
  Realtime. No login/auth pages — the app is open to all visitors.

- **Phase 8 — Performance, Polish & Deployment**
  Caching refinements, concurrency tuning, error handling/observability,
  deployment (frontend + backend + Supabase config), final QA across devices.

Phases can be renumbered/split further as implementation reveals complexity
(e.g. Phase 1 may itself be split into 1a-ingestion and 1b-claim-detection if
useful) — any such change gets recorded in `logs.md`.

---

## 12. Open Decisions (to resolve as we hit them, tracked here until settled)

- [ ] Exact ASR model/service (local Whisper vs hosted API) — cost/speed tradeoff.
- [ ] Exact claim-detection approach (fine-tuned classifier vs LLM-prompted
      extraction vs hybrid) for Phase 1.
- [ ] LLM provider/model for claim detection prompting and for the LangGraph
      verification agent.
- [ ] Retrieval tools for the agent: general web search API + a
      medical-specific source (PubMed API / semantic scholar / etc).
- [ ] Whether uploaded media is retained in Supabase Storage or discarded
      after hashing + processing (privacy/storage-cost tradeoff).
- [ ] Background job mechanism: stick with FastAPI BackgroundTasks or move to
      Celery/Arq + Redis — decide based on Phase 1 load testing.
