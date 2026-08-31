# AI Image Understanding & Content Matching Engine

FlyRank Internship · Backend Track · Capstone

Tags a small image library with a vision model, embeds images and blog
posts into a shared semantic space, ranks the best image for each post —
and, most importantly, **refuses a wrong pairing** instead of guessing. A
red-fox post gets a red-fox photo; a gray-wolf photo is provably rejected;
a post with no good match gets told so, with a reason.

```
docs/capstone-brief.pdf   <- the assignment brief this repo implements
DESIGN.md                 <- Phase 1 design doc (data model, guard rules, API surface)
EVIDENCE.md               <- one pasted proof per requirement checkbox
BUILDLOG.md               <- honest AI-usage log
```

## Architecture

```
                 ┌──────────────────────┐
 data/corpus/ -->│ POST /images/batch/  │--> Image.{subject,category,attributes,
 (batch job)     │  classify (vision)   │     caption,confidence,tag_status}
                 └──────────┬───────────┘        │
                            │ embed(caption+tags) │ tag_status=invalid -> excluded
                            v                     v
                     Image.embedding[]     (never embedded, never suggested)

 Post.{title,body} --embed(title+body)--> Post.embedding[]

 GET /posts/:id/images
   └─> Similarity Ranking      (cosine(post.embedding, image.embedding) for every image)
        └─> Mismatch Guard     (app/guard.py: category match via post-text keyword
             │                  extraction + model-detected subject, AND similarity
             │                  >= threshold)
             ├─ accepted, ranked ──> Suggestion(status=accepted, rank, reason)
             ├─ rejected ──────────> Suggestion(status=rejected, reason)     <- always has a reason
             └─ nothing cleared ───> Suggestion(status=no_match, reason)
                    │
                    v
             GET/POST /review/*   (approve / reject / inspect why)
```

Every vision and embedding call is logged to `api_call_log` (see
`GET /costs/summary`), and every batch run (vision tagging, embedding,
matching) is tracked in `batch_jobs`/`batch_job_items` with per-item retry
counts (`GET /batch/jobs`).

## Stack ($0, no credit card — brief section 10)

| Need | Choice |
|---|---|
| Language + framework | Python 3.12 + FastAPI |
| Vision model | Gemini 2.5 Flash (free tier, Google account only) — or fully local Ollama (`moondream`/`llava`), select via `VISION_PROVIDER` |
| Embeddings | Gemini `gemini-embedding-001` — or local Ollama `all-minilm` |
| Schema validation | Pydantic |
| Database | PostgreSQL via Docker, plain `float[]` columns for embeddings (fine at ~50 images) |
| Image corpus | Wikimedia Commons (no API key required, CC/public-domain licensed; license recorded per image in `data/manifest.json`) — see "A note on the image source" below |
| Migrations | Alembic |

## Run it

Requires Docker + Docker Compose. One command boots the whole system on a
clean machine:

```bash
cp .env.example .env
# edit .env and set GEMINI_API_KEY (free key: https://aistudio.google.com/apikey)
# or set VISION_PROVIDER=ollama / EMBEDDING_PROVIDER=ollama to run fully local

docker compose up --build
```

This starts Postgres, runs Alembic migrations, and serves the API on
`http://localhost:8000` (interactive docs at `/docs`).

### Seed step (demo data)

In a second terminal, once the stack is up:

```bash
docker compose exec app python -m scripts.seed_corpus
```

Downloads ~50 licensed-free images across 5 categories (fox, wolf, dog,
bear, deer) from Wikimedia Commons and loads the 12 hand-labeled blog
posts from `data/eval_set.json`. Images are *not* committed to the repo
(brief: "don't commit datasets over a few MB") — this script is the
reproducible download step instead; `data/manifest.json` (which *is*
committed) records exactly what was downloaded and under what license.

### Run the pipeline

```bash
curl -X POST http://localhost:8000/images/batch/classify   # vision tagging (async)
curl -X POST http://localhost:8000/images/batch/embed      # image embeddings (async)
curl -X POST http://localhost:8000/posts/batch/embed       # post embeddings (async)
curl -X POST http://localhost:8000/posts/batch/match       # rank + guard -> Suggestion rows

curl http://localhost:8000/batch/jobs                      # watch progress
curl http://localhost:8000/posts/1/images                  # ranked, guard-checked suggestions
curl http://localhost:8000/costs/summary                   # per-call cost tracking
```

### Evaluate

```bash
docker compose exec app python -m scripts.run_eval
```

Prints top-1 precision against the hand-labeled eval set — see
`EVIDENCE.md` for the actual run.

### Tests

```bash
docker compose exec app pytest -q
```

`tests/test_guard.py` exercises the exact fox/wolf scenario from the
brief without any DB — pure function in, pure decision out.

## A note on the image source

The brief suggests Unsplash/Pexels; both require a free API key. This repo
uses the Wikimedia Commons search API instead, which needs **no key at
all** and serves openly licensed (CC-BY-SA / public domain) images — a
strictly lower-friction fit for the "$0, no credit card, ever" constraint.
Every downloaded image's specific license is recorded in
`data/manifest.json`. Logged as a deliberate deviation in `BUILDLOG.md`.

## Limitations (honest, per brief section 11)

- **Single tenant, no auth.** This is an internal review tool, not a
  multi-customer product — see `DESIGN.md`'s explicit non-goal.
- **One vision model, one embedding model.** Comparing providers was
  explicitly called out as a stretch goal, not core scope.
- **Category vocabulary is a small, hardcoded synonym table**
  (`app/guard.py: CATEGORY_KEYWORDS`), sized to the 5-category demo
  corpus. A production system would need a much larger taxonomy or a
  second model call to extract the expected subject from arbitrary post
  text.
- **Background jobs run in-process** (FastAPI `BackgroundTasks` + a
  synchronous retry loop), not on a separate worker/queue — correct at
  this scale (≤50 images, seconds of work) but wouldn't scale to a large
  corpus without moving to Celery/RQ + Redis.
- **No frontend.** Per brief section 4.5, the review "UI" is the
  `/review/*` API surface plus the `suggestions`/`review_decisions`
  tables, inspectable via `/docs` or `curl`.
