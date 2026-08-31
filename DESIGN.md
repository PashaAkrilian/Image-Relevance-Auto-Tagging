# Design doc — AI Image Understanding & Content Matching Engine

*(Phase 1 gate, brief section 8.1: problem, data model, API surface, layer
sketch, one explicit non-goal.)*

## Problem

Given a small library of images and a set of blog posts, tag every image
with structured, validated metadata; embed images and posts into a shared
semantic space; rank the best-matching images for each post; and — the
production-critical part — run every ranked candidate through a **mismatch
guard** that refuses a wrong pairing (fox post + wolf photo) and says "no
confident match" rather than guessing when nothing clears the bar.

## Data model

```
Image            Post              Suggestion                  ReviewDecision
-----            ----              ----------                  --------------
id               id                id                          id
category*        title             post_id -> Post             suggestion_id -> Suggestion (1:1)
file_path        body              image_id -> Image (null)    decision (approved/rejected)
source_url       expected_        similarity_score             note
license           category*        rank                        created_at
subject           (eval only)      status (accepted/            *only ever read by
tag_category      embedding[]       rejected/no_match)           scripts/run_eval.py,
attributes[]      created_at       reason (always populated)     never by the guard
caption                            created_at
confidence
tag_status (pending/valid/flagged/invalid)
tag_error
embedding[]
created_at

BatchJob / BatchJobItem            ApiCallLog
-------------------------          ----------
job_type, status,                  provider, task_type,
total/completed/failed_items,      related_type/id,
started_at/finished_at             units, cost_usd, created_at
items[] (per-item retry trail)
```

`*` = ground-truth corpus label (`Image.category`) and hand-authored eval
label (`Post.expected_category`) are both "answer key" fields, kept
separate from what the *model* produces (`Image.subject`/`tag_category`,
which the guard actually reasons over) and separate from what the *guard*
infers at run time from post text (`app.guard.extract_expected_category`).
This separation is what makes `scripts/run_eval.py` a real, non-circular
check.

## Matching strategy & guard rules

1. **Structured output.** Every image is sent to the vision model with a
   prompt asking for JSON matching `VisionTagSchema` (subject, category,
   attributes, caption, confidence). The response is validated with
   Pydantic; on failure it's retried (schema-conforming JSON is
   occasionally sloppy on the first try), and after `BATCH_MAX_RETRIES`
   failures the image is marked `tag_status=invalid` and is excluded from
   every later step — it is never embedded and can never become a
   suggestion.
2. **Confidence flag.** A schema-valid response with `confidence` below
   `VISION_CONFIDENCE_THRESHOLD` is stored but marked `tag_status=flagged`
   — visible for human review rather than silently accepted as ground
   truth.
3. **Embeddings.** Each image's caption + subject + attributes, and each
   post's title + body, are embedded with the same model into one vector
   space (`SEMANTIC_SIMILARITY` task type). Cosine similarity ranks every
   image against a post.
4. **Mismatch guard** (`app/guard.py`), run over every ranked candidate:
   - Extract the post's expected subject from its own text via a small
     keyword/synonym table (`fox`/`foxes`/`vulpes vulpes` → `fox`, etc.) —
     this is how "red fox", "Vulpes vulpes", and "wild fox species" all
     resolve to the same category.
   - Canonicalize the candidate's *model-detected* subject/category the
     same way.
   - Reject if categories don't match (or the candidate's category can't
     be resolved at all — an unverifiable match is refused, not guessed).
   - Reject if cosine similarity is below `SIMILARITY_THRESHOLD`.
   - Otherwise accept, and rank accepted candidates by similarity.
   - If literally nothing clears both bars, emit a single `no_match`
     decision with the specific reason (best similarity seen, or "no
     images available").
   - Every decision — accepted, rejected, or no-match — carries a
     human-readable `reason` string. Nothing is ever silent.

## API surface

```
GET  /health
GET  /images                         list images (+ ?tag_status filter)
GET  /images/{id}
POST /images/batch/classify          kick off the vision batch job (async)
POST /images/batch/embed             kick off the image embedding batch job (async)

GET  /posts
GET  /posts/{id}
GET  /posts/{id}/images              ranked, guard-checked suggestions + best_match
POST /posts/batch/embed              kick off the post embedding batch job (async)
POST /posts/batch/match              run the guard over every post -> persists Suggestion rows

GET  /review/pending                 accepted suggestions with no review decision yet
GET  /review/suggestions/{id}        inspect why a suggestion was accepted/rejected
POST /review/suggestions/{id}/decision   approve / reject

GET  /batch/jobs                     job list with progress
GET  /batch/jobs/{id}

GET  /costs/summary                  per-provider/task cost + call counts
```

## Layer sketch

```
routers/ (HTTP, validation at the boundary)
   -> jobs/ (batch orchestration: retries, progress, cost logging)
        -> vision/, embeddings/ (provider-agnostic interfaces; gemini_provider.py / ollama_provider.py)
        -> guard.py, matching.py (pure functions, no DB/HTTP -- directly unit-testable)
   -> models.py / db.py (SQLAlchemy + Alembic migrations)
```

`guard.py` and `matching.py` take plain Python values in and return plain
Python values out — no ORM objects, no HTTP — specifically so
`tests/test_guard.py` can exercise the exact fox/wolf scenario from the
brief without a database.

## Explicit non-goal

**Multi-tenancy / multi-user auth is out of scope.** This is a single-
operator internal tool (brief: "a simple admin table, or a minimal internal
page — no frontend build"). The schema has no `tenant_id`/`user_id`
columns and the API has no auth layer; adding both would be the first
change needed before this became a multi-customer product.
