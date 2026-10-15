# FACTCHECKER — Progress Log



## Status Overview

| Phase | Description | Status |
|---|---|---|
| 1 | Ingestion | ✅ Done |
| 2 | Claim Review & Editing | ✅ Done |
| 3 | Claim Processing (canonicalization) | 🟡 In progress (3.1 complete; 3.2–3.3 pending) |
| 4 | Agentic Verification (LangGraph) | 🔲 Not started |
| 5 | Result Aggregation & Persistence | 🔲 Not started |
| 6 | Rate Limiting & Abuse Protection | 🔲 Not started |
| 7 | Backend Performance, Reliability & Deployment | 🔲 Not started |

Legend: 🔲 Not started · 🟡 In progress · ✅ Done

---

## Entries

### [Planning] — 2026-09-22

- Reviewed the workflow diagram PDF and the full project brief.
- Wrote `context.md` covering: two-mode system (General/Medical), backend
  processing flow, architecture (FastAPI + Supabase), draft DB schema, the
  LangGraph agentic verification design, caching strategy (URL/content-hash,
  scoped per mode), auth/route-protection plan, non-functional requirements,
  and the backend implementation roadmap.
- Decided: only the verification stage is agentic (LangGraph); ingestion →
  claim detection stays a deterministic NLP pipeline for speed/predictability.
- Decided: caching key is `(raw_url or content_hash, mode)` — same content in
  a different mode is treated as a separate cached result.
- Open decisions logged in `context.md` §12 (ASR choice, claim-detection
  approach, LLM provider, retrieval tools, media retention, background job
  mechanism) — to be resolved at the start of Phase 1.

**Next step:** Begin Phase 1 — backend scaffolding for input handling
(URL / mp4 / mp3 / text) through to claim list generation.

---

### [Planning — revision] — 2026-09-22

- User decision: **no user data is stored, ever.** Supabase is used purely as
  a cache/lookup store keyed by input URL, hashed text, or content hash of
  uploaded audio/video (the media file itself is never persisted — hashed,
  processed, then discarded).
- Updated `context.md`:
  - §4.3 — `submissions` table is now a shared cache table with no user
    linkage; Supabase Storage is not used at all.
  - §5 — DB schema: removed `user_id` from `submissions`; added `text_hash`
    (sha256 of `raw_text`) so text inputs get the same fast-lookup cache
    behavior as URLs and media hashes; added indexes for all three lookup
    keys (`raw_url`, `content_hash`, `text_hash`), each scoped by `mode`.
  - §8 — Reframed auth: Supabase Auth is a login gate to block unauthorized/
    anonymous API use only — it is explicitly decoupled from data storage,
    never attaches identity to a submission.

**Next step:** unchanged — Phase 1 (Ingestion → Claim Detection backend
core), starting with resolving the open decisions in `context.md` §12.

---

### [Planning — revision] — 2026-09-22 (2)

- User decision: **remove the auth layer completely.** No Supabase Auth,
  session handling, or user identity is part of the backend. Processing
  endpoints remain publicly accessible.
- Only protection needed is against DDoS/abuse — implemented purely as
  **rate limiting** on the processing endpoints (ingestion/verification),
  IP-based, via a lightweight middleware (`slowapi` or Redis-backed counter).
- Updated `context.md`:
  - §4 architecture diagram — dropped the Auth box from Supabase, backend box
    now notes "rate-limited endpoints" instead of an auth-gated ones.
  - §4.2 — route protection line now points to rate limiting only.
  - §4.3 — Supabase is Postgres-only, no Auth, no Storage; explicit "no auth
    system at all" statement.
  - §8 — fully rewritten: "Route Protection (Rate Limiting Only — No Auth
    Layer)". No login, no JWT, no identity. Just per-IP rate limits on the
    expensive endpoints.
  - §9 non-functional requirements — security bullet now reads: rate limiting
    + input validation only.
  - Tech stack table — replaced "Database / Auth" row with a plain "Database"
    row (Postgres cache table only) and added a new "Rate limiting" row.
  - §11 — Phase 6 renamed "Route Protection (Rate Limiting)", no longer an
    auth phase.

**Next step:** unchanged — Phase 1 (Ingestion → Claim Detection backend
core), starting with resolving the open decisions in `context.md` §12.

---

### [Phase 1] - START 2026-09-24

---

### [Phase 1] — 2026-09-25

Backend scaffolding is in place using FastAPI:-

- app/main.py creates the Factchecker API FastAPI application.
  - GET / provides a basic API-running response.
  - GET /health provides a basic backend health check.
- Supabase connectivity scaffolding is implemented:
  - app/core/supabase.py creates a Supabase client using SUPABASE_URL and SUPABASE_SERVICE_KEY.
  - GET /health/supabase checks connectivity by querying the submissions table.
- Environment/config scaffolding is implemented in app/core/config.py using python-dotenv.
  - Config entries exist for Supabase credentials, Groq API key, Whisper model, and Groq LLM model configuration.
  - .env.example documents the expected environment variables and currently defaults Whisper to whisper-large-v3-turbo and the LLM to llama-3.3-70b-versatile.
- Project structure has been started with separate api, core, schemas, services, and tests packages, leaving room for the planned modular architecture.
- requirements.txt currently contains the installed/base FastAPI + Supabase/Python dependency set. The actual ingestion, ASR, claim-detection, and NLP-specific dependencies are not yet represented in the current setup.
- Temporary media handling is anticipated in the repository (temp_media/ is present and ignored by Git), but no ingestion/download/audio-extraction implementation is present yet.

**Supabase database setup completed:**

- Created the `submissions` table with fields for `input_type`, `mode`, `raw_url`, `content_hash`, `raw_text`, `text_hash`, `status`, and `created_at`.
- Added database constraints restricting `input_type` to `text`, `audio`, `video_url`, or `video_file`.
- Added database constraints restricting `mode` to `general` or `medical`.
- Added a `status` constraint covering the planned processing states: `pending`, `processing`, `claims_ready`, `verifying`, `done`, and `failed`.
- Created the `claims` table linked to `submissions` through `submission_id` with `ON DELETE CASCADE`.
- `claims` contains the planned fields for canonical claim text, original source span, inclusion state, verdict, confidence, explanation, evidence JSON, and timestamp.
- Created the three cache uniqueness indexes, all scoped by `mode`:
  - `submissions_url_mode_uidx` on `(raw_url, mode)` for URL-based submissions.
  - `submissions_hash_mode_uidx` on `(content_hash, mode)` for uploaded audio/video content.
  - `submissions_texthash_mode_uidx` on `(text_hash, mode)` for text submissions.
- The implemented database structure now matches the Phase 1 schema specified in `context.md` and supports the planned mode-specific cache lookup strategy.

**Status at this point:**

- No Phase 1 API for submitting text/audio/video/URL exists yet.
- No yt-dlp downloader, audio extraction pipeline, ASR transcription pipeline, claim-detection pipeline, cache lookup logic, or claim-list generation has been implemented yet.
- No Supabase schema/migration file is present in the submitted backend ZIP, so the planned submissions/claims schema from context.md is not yet represented as backend code or migrations in this setup.
- Phase 1 remains 🟡 In progress. The current work is backend foundation/scaffolding, not yet the full Phase 1 ingestion → claim-detection flow.

**Next step:** implement the Phase 1 ingestion layer, starting with the text input path and the submission API, then add URL/video/audio handling, ASR, claim detection, and the planned cache lookup/schema integration incrementally.

---

### [Phase 1 — Complete] — 2026-09-30

- Completed Phase 1 — Ingestion → Claim Detection (backend core).
- Finalized the main Phase 1 implementation choices:
  - ASR: Groq Whisper API using whisper-large-v3-turbo.
  - Claim detection approach: classic NLP/ML using
    facebook/bart-large-mnli together with the planned hybrid approach using
    BART-MNLI + Groq LLM.
  - LLM provider/model: Groq with llama-3.3-70b-versatile.
  - URL downloading: yt-dlp.
  - Audio extraction: FFmpeg/FFprobe
- Implemented the ingestion layer for:
  - plain text input
  - uploaded audio files
  - uploaded video files
  - supported video URLs
- Implemented media validation for supported file extensions, maximum file
  size, and maximum media duration.
- Implemented SHA-256 content hashing for uploaded media.
- Implemented temporary media storage and cleanup so media is not persisted
  after processing.
- Implemented supported URL validation and downloading for YouTube, Instagram,
  and Facebook using yt-dlp.
- Implemented video-to-audio extraction using FFmpeg.
- Implemented FastAPI ingestion endpoints and request schemas for the Phase 1
  input paths.
- Supabase connectivity and the Phase 1 cache schema are working.
- Verified ingestion for text, uploaded audio, uploaded video, and a supported
  video URL.
- No media files are permanently stored; temporary media is processed and
  cleaned up.
- Phase 1 is now complete and the backend ingestion pipeline is ready for
  Phase 2.

**Next step:** Begin Phase 2 — Claim Review & Editing.

### [Phase 2 — Complete] — 2026-09-30

- Completed Phase 2 — **Claim Review & Editing**.

- Finalized the Phase 2 approach:
  - Reviewed claims remain in the same `claims` table row.
  - `claim_text` stores the current/reviewed version of the claim.
  - `original_span` remains reserved for the original source span from which
    the claim was extracted.
  - Added `original_claim_text` to preserve the exact Phase 1 claim so that
    edited claims can always be restored.
  - No separate claim-review table was introduced.

- Implemented claim management operations:
  - Include a claim.
  - Exclude a claim.
  - Edit a claim.
  - Restore the original claim.
  - Add a new claim.
  - Delete a manually added claim.
  - Reorder/manage the reviewed claim list as part of the review workflow.
  - Confirm the final set of included claims for the next phase.

- Implemented NLP validation specifically for **edited claims**.
  - Phase 2 does not perform claim canonicalization.
  - Canonicalization and deeper NLP processing remain part of Phase 3.
  - Implemented BART-MNLI validation using `facebook/bart-large-mnli`.
  - Implemented a separate hybrid validation function using BART-MNLI +
    Groq LLM for future use.
  - The validation strategy can be switched through configuration without
    changing the claim-review service logic.
  - Invalid edited claims are rejected and the existing claim remains
    unchanged.

- Implemented claim-review backend structure:
  - Claim review API router.
  - Claim request/response schemas.
  - Claim management service.
  - Pluggable claim validation service.
  - Configuration for selecting the edit-validation strategy.

- Implemented the following claim-review API operations:
  - `GET /claims/submission/{submission_id}` — retrieve claims for a submission.
  - `POST /claims/{claim_id}/include` — include a claim.
  - `POST /claims/{claim_id}/exclude` — exclude a claim.
  - `PUT /claims/{claim_id}` — edit and validate a claim.
  - `POST /claims/{claim_id}/restore` — restore the original claim.
  - `POST /claims/submission/{submission_id}/add` — add a manual claim.
  - `DELETE /claims/{claim_id}` — delete a manually added claim.
  - `POST /claims/confirm` — confirm the reviewed claim set for Phase 3.

- Detected Phase 1 claims are not permanently deleted during review.
  Excluding a detected claim changes its `included` state so the original
  claim remains recoverable.

- Manual claims can be permanently deleted.

- Phase 2 is now **complete** and the reviewed claim set is ready to be passed
  into Phase 3.

- **Next step:** Begin Phase 3 — Claim Processing (Canonicalization).

- **Imp** Phase 3 is divided into 3 subphases 3.1,3.2,3.3 - 2026-10-01
   3.1 will act between phase 1 and phase 2 (if refered according to app workflow)
   it is responsible for generating the initial candidate claims list
   3.2 and 3.3 will then work later on claim processing
   More Details:
   During the transition from Phase 2 to Phase 3, it was clarified that the initial candidate claim extraction had not actually been implemented as part of Phase 1. Phase 1 was completed as the input ingestion layer, covering input validation, media handling, hashing, transcription/extraction, temporary processing, URL downloading, and cache connectivity. Phase 2 implemented the claim review and editing operations but assumes that an initial candidate claim list is provided to it. 
   Therefore, Phase 3 will begin with the missing initial candidate claim extraction stage. Phase 3.1 will extract potential candidate claims from the processed input/transcript and pass them to the existing Phase 2 review workflow. The later stages of Phase 3 will then classify whether the candidates are genuine verifiable claims and canonicalize the approved claims before they are passed to Phase 4 for agentic verification.
---

### [Phase 3.1 — Initial Candidate Claim Extraction] — 2026-10-12

- Began Phase 3.1 to implement the missing initial candidate claim extraction stage. This stage sits between Phase 1's processed input/transcript and Phase 2's existing claim review workflow.
- Finalized a configurable extraction design with two strategies:
  - **Option A — NLP/ML:** sentence segmentation followed by BART-MNLI zero-shot classification using `facebook/bart-large-mnli` to identify potential factual statements.
  - **Option C — Hybrid:** BART-MNLI generates initial candidates, then Groq using `llama-3.3-70b-versatile` reviews/refines the candidate list.
- Added configuration through `CLAIM_EXTRACTION_STRATEGY` (`nlp` or `hybrid`) and `CLAIM_EXTRACTION_THRESHOLD`, allowing the strategy and candidate threshold to be changed without rewriting the extraction service.
- Added a candidate-claim response schema containing `claim_text`, `original_span`, and optional confidence, along with submission-level extraction response metadata.
- Added a shared extraction service that selects the configured strategy and exposes a common extraction interface.
- Added the planned endpoint `POST /claims/extract/{submission_id}` to retrieve the submission's processed `raw_text`, extract candidate claims, store them in the existing `claims` table, update the submission status to `claims_ready`, and return the generated list.
- Candidate claims are intended to be available to the existing Phase 2 APIs for inclusion, exclusion, editing, restoration, adding, deleting, and confirmation.
- Phase 3.1 only generates potential candidates. It does not perform final claim-vs-non-claim classification or canonicalization; those remain later Phase 3 stages.

---

### [Phase 3.1 — Complete] — 2026-10-15

- Completed end-to-end testing of the Phase 1 → Phase 3.1 → Phase 2 flow.
- Verified ingestion, candidate-claim extraction from processed `raw_text`, persistence in the `claims` table, and the Phase 2 claim-review operations.
- Phase 3.1 is complete and working as expected.

**Next step:** Begin Phase 3.2 — classify reviewed candidate claims as verifiable claims before canonicalization in Phase 3.3.

 - Needs better fine tuning of Bart Labels and threshold and tokenization of splitting of raw text (which comes from speech to text after ASR) into sentences since for many shorts it is not able to pick up all the facts, I suggest we keep the threshold low and allow a lot of claims to be detected so that we dont miss any crucial ones. Since the user has the power to exclude it makes sense to detect all

 Thus upgrading or modifying the worflow uptill now that is the [ ingestion->extraction->candidate claims display] this work is still pending
---

<!-- Add new entries above this line -->
