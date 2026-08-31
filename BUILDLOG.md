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
