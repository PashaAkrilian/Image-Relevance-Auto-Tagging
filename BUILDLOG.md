# Build log — honest AI-usage notes

Per brief section 3: "AI-assisted building is encouraged and owned." This
entire repository was built by Claude (Anthropic's Claude Code) working
autonomously from `docs/capstone-brief.pdf`, at the repo owner's direction.
This log records where AI helped, where it was wrong or had to backtrack,
and what a reviewer should know about how the code came to be.

## Where AI helped

- **Everything.** Architecture, schema, the vision/embedding provider
  abstraction, the mismatch guard logic, the batch job runner, the FastAPI
  routers, the Wikimedia Commons corpus downloader, the eval script, tests,
  and this documentation were all written by Claude in one continuous
  session, then run and debugged against the real Gemini API and a real
  Postgres instance rather than left unverified.

## Where it was wrong / had to change

- **Vision model name.** The brief and most Gemini docs reference
  `gemini-2.5-flash`; live-tested against the real API it returned
  `404 NOT_FOUND — no longer available to new users`. Listed the account's
  actually-available models via `client.models.list()` and switched to
  `gemini-3.6-flash` (config default in `app/config.py`, overridable via
  `GEMINI_VISION_MODEL`). `gemini-flash-latest` was tried first and returned
  transient `503 UNAVAILABLE` (high demand) on every attempt during
  development, so the pinned model name was kept instead of the alias.
- **`uvicorn[standard]`** pulls in a `pyyaml` version whose build backend
  is incompatible with Python 3.14 (`AttributeError: 'build_ext' object has
  no attribute 'cython_sources'`). Fixed by installing plain `uvicorn` and
  pinning `pyyaml>=6.0.2` directly (see `requirements.txt`) — the app
  doesn't touch uvicorn's optional extras (uvloop/httptools/watchfiles) so
  nothing was lost functionally.
- **First unit test assertion was wrong**, not the guard: `run_guard`
  correctly returns a leading `no_match` placeholder whenever nothing gets
  accepted, so a single-rejected-candidate case returns 2 decisions, not 1.
  Fixed the test's expectation rather than the guard.
- **Host port 5432 was already taken** by an unrelated Postgres container
  on this shared dev machine. `docker-compose.yml` maps the db service to
  host port `5433` instead (internal container-to-container traffic on the
  Docker network is unaffected and still uses 5432).
- **`gemini-3.6-flash` has a 20-requests/day free-tier quota.** Discovered
  mid-run: the vision batch job succeeded on 18/50 images, then every
  remaining call returned `429 RESOURCE_EXHAUSTED ... limit: 20 ...
  GenerateRequestsPerDayPerProjectPerModel-FreeTier`. Switched the default
  vision model to `gemini-3.1-flash-lite`, which has a materially higher
  free-tier quota and classified the other 32 images with zero failures.
  This also motivated making `POST /images/batch/classify` resumable
  (only queries `tag_status=pending` images) instead of always re-queuing
  everything — see `app/routers/images.py`.
- **A transient DNS blip mid-embedding-batch** (`[Errno -3] Temporary
  failure in name resolution`, this dev sandbox's network, not Gemini)
  failed 11/50 image embeddings after 3 retries each. Made
  `POST /images/batch/embed` and `POST /posts/batch/embed` resumable the
  same way (only queries rows with `embedding IS NULL`) and re-ran; all 11
  succeeded on retry with no code changes needed — this is the
  idempotency design in `DESIGN.md` actually being exercised, not just
  asserted.
- **`SIMILARITY_THRESHOLD` default (0.55) was too permissive.** Once a
  deliberately off-topic "cloud infrastructure" post was pushed through
  the live pipeline to prove out the "no confident match" behavior (PROBE
  4), it scored 0.71 similarity against an unrelated animal photo and got
  *accepted* — `gemini-embedding-001` puts most English text pairs in a
  fairly narrow cosine-similarity band, so 0.55 was never actually
  screening anything out. Recalibrated to 0.715 against the real observed
  distribution (min accepted-match similarity across every real category
  vs. the off-topic post's best score) — see `DESIGN.md` "Threshold
  calibration". Re-ran the eval script afterward to confirm the 12/12
  labeled posts were unaffected.

## Deliberate deviation from the brief, logged for transparency

- **Image source: Wikimedia Commons instead of Unsplash/Pexels.** Both
  suggested sources require a free API key/signup; Commons' MediaWiki
  search API needs none and licenses (recorded per-image in
  `data/manifest.json`) are still clearly open (CC-BY-SA/public domain).
  See README "A note on the image source".
- **Corpus not committed to git**, only the download script
  (`scripts/seed_corpus.py`) and its resulting `data/manifest.json` are —
  per the brief's own "don't commit datasets over a few MB" rule and its
  "commit it (or a download script)" alternative.

## What a reviewer should be able to ask me about any file

Any 2-3 lines of this codebase can be explained: why the guard is a pure
function with no DB access (`tests/test_guard.py` needs to exercise it
without a database), why `tag_status=invalid` images are filtered out
*before* the guard even runs (`app/jobs/matching_job.py`) rather than only
inside the guard (defense in depth — an invalid-tag image should never even
become a candidate), why cost tracking logs a row even when `cost_usd=0.0`
(the free tier doesn't change the requirement to attribute every call), and
why `Post.expected_category` and `app.guard.extract_expected_category` are
two independent code paths rather than one shared function (so
`scripts/run_eval.py` isn't circularly grading the guard against its own
logic).
