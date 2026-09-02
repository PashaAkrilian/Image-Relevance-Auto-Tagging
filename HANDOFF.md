# Handoff

Status as of **2026-09-01**, repo:
https://github.com/PashaAkrilian/Image-Relevance-Auto-Tagging (branch `main`)

## TL;DR

The capstone (`docs/capstone-brief.pdf`) is **built, run against the real
Gemini API, verified via a clean `docker compose up --build`, and
pushed**. Every Section 6 requirement checkbox has a real, pasted proof in
`EVIDENCE.md`. **The only thing left is the human step**: submit the repo
URL through the FlyRank internship portal (brief section 12) — that's a
web form on their platform, not something doable from here.

## What's in the repo

| File | Purpose |
|---|---|
| `README.md` | What the system does, architecture diagram, run steps, results (100% top-1 precision) |
| `DESIGN.md` | Data model, guard rules, API surface, threshold calibration rationale, one explicit non-goal |
| `EVIDENCE.md` | One real, pasted proof per requirement checkbox — read this first to verify the claims below |
| `BUILDLOG.md` | Every real incident hit while building (quota limits, a DNS blip, a stalled-connection hang, a 500-instead-of-422 bug) and how each was fixed — the honest AI-usage log the brief requires |
| `capstone.yaml` | Evaluator manifest (run/seed/test commands, endpoint list) |
| `app/` | FastAPI app (routers, guard, matching, vision/embedding providers, batch jobs) |
| `scripts/seed_corpus.py` | Downloads the 50-image corpus from Wikimedia Commons (no API key) + loads `data/eval_set.json` |
| `scripts/run_eval.py` | Prints top-1 precision against the hand-labeled eval set |
| `tests/` | 19 tests, all passing — `test_guard.py` reproduces the exact fox/wolf scenario from the brief with no DB |

## Commit history (4 commits, one per build phase)

```
491fdc9 Fix: tag_status query param validated at the boundary (was a 500, now 422)
91a76e7 Phase 4: production layer verified via clean docker compose run + evidence
f03b748 Phase 2+3: real vision/embedding/matching pipeline run + calibrated guard
e4e6be1 Phase 1: design doc, schema, migrations, guard/matching core + tests
```

## Verified results (real numbers, see EVIDENCE.md for the full pasted proof)

- **Top-1 precision: 12/12 = 100%**, reproduced twice independently (once
  in a local dev venv, once from a completely clean `docker compose up
  --build`).
- 50/50 images classified, schema-validated, never silently trusted on
  failure.
- 4/50 images flagged for low confidence in the primary evidence run
  (mixed-model run — see the confidence-variability note in `BUILDLOG.md`).
- Wolf/dog/bear/deer images are provably rejected on fox posts with a
  human-readable reason; an off-topic post correctly gets "no confident
  match".
- Every vision/embedding call attributed in `api_call_log` (113 calls,
  $0.00 — free tier).
- `docker compose exec app pytest -q` → 19/19 passing.

## Local environment state (this sandbox only — not needed for the repo to work elsewhere)

- `.env` (git-ignored) holds a real `GEMINI_API_KEY` already exported in
  this shell's environment — **do not commit it**.
- A `docker compose` stack is currently **up** in this sandbox
  (`imagerelevanceauto-tagging-app-1` on `:8000`,
  `imagerelevanceauto-tagging-db-1` on `:5433`) with a fully-seeded,
  fully-processed database behind it — useful for poking at the live API
  (`curl http://127.0.0.1:8000/docs`) without re-running the pipeline.
  Bring it down with `docker compose down` (add `-v` to also drop the
  seeded data) when done.
- A separate standalone `postgres:16-alpine` container
  (`capstone-pg`, port `5433`) was used earlier for local-venv iteration
  and has since been removed — only the compose-managed `db` service
  remains.
- A Python venv at `.venv/` (git-ignored, Python 3.14) exists for running
  things outside Docker (`. .venv/bin/activate && pytest -q`).

## Known gotchas if you touch this again (all documented in BUILDLOG.md)

1. **`gemini-3.6-flash` has only a 20-requests/day free-tier quota.**
   The default vision model is `gemini-3.1-flash-lite`
   (`GEMINI_VISION_MODEL` in `.env`) specifically to avoid this.
2. **Gemini's self-reported confidence varies noticeably across
   runs/models.** `VISION_CONFIDENCE_THRESHOLD` (0.93) and
   `SIMILARITY_THRESHOLD` (0.715) are calibrated against one real run,
   documented in `DESIGN.md` "Threshold calibration" — re-tune if you
   re-run against a different model or a bigger corpus and nothing gets
   flagged / everything gets accepted.
3. **This sandbox's network is occasionally flaky** (transient DNS
   failures hit both `pip install` inside the Docker build and a live API
   call mid-batch). The batch runner retries 3x with backoff and the
   `POST /images(or posts)/batch/*` endpoints are resumable — safe to
   just re-call them.
4. Gemini API calls now have an explicit 45s client timeout
   (`app/vision/gemini_provider.py`, `app/embeddings/gemini_embeddings.py`)
   after a stalled connection once hung a worker thread indefinitely with
   no timeout set.

## If you pick this back up

- To re-verify from absolute zero: `docker compose down -v`, then follow
  `README.md`'s "Run it" section top to bottom.
- To extend it: `DESIGN.md`'s "Explicit non-goal" and README's
  "Limitations" section list what was deliberately left out (multi-tenant
  auth, multiple vision/embedding models, a real job queue) — all
  reasonable next steps, none required by the brief.
- The brief's stretch goals (section 9) — alt-text generation, near-dup
  detection, fallback image generation, human-in-the-loop agent QA, a
  bigger test suite — are unstarted; the core was prioritized end-to-end
  over any one stretch goal, per the brief's own guidance ("a finished
  core with one polished stretch beats three half-stretches").
