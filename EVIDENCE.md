# Evidence

One pasted proof per requirement checkbox (brief section 6). All output
below is real, captured from an actual run against the live Gemini API and
a real Postgres instance — the 50-image corpus, 12 hand-labeled posts, and
1 deliberate no-match probe post, exactly as `README.md`'s run steps
describe. See `BUILDLOG.md` for two real incidents hit and fixed during
this run (a vision model's tiny free-tier daily quota, and a transient DNS
blip mid-embedding-batch) — both are also proof that the retry/resume
machinery below is real, not theoretical.

**Independently re-confirmed via the actual documented path**: a clean
`docker compose up --build` + `docker compose exec app python -m
scripts.seed_corpus` + the same batch/eval calls, from scratch, against a
fresh containerized Postgres, reproduced 50/50 images classified, 63/63
embeddings, **12/12 (100%) eval precision**, and 19/19 tests passing (see
`BUILDLOG.md` "Docker Compose validation run" — this run also surfaced and
fixed a real client-timeout gap in the vision/embedding providers).

---

## AI processing

### ✅ Vision model produces structured output validated against a schema; invalid responses are never trusted

`tests/test_schema.py` (9 tests) exercises `VisionTagSchema` against valid
and invalid payloads directly:

```
$ pytest -q tests/test_schema.py
.........                                                               [100%]
9 passed in 0.08s
```

A real Gemini response for `data/corpus/fox/fox_07.jpg`, parsed and
schema-validated (`app/jobs/vision_job.py`):

```json
{
  "subject": "red fox kit",
  "category": "animal",
  "attributes": ["red fox", "kit", "grass", "boulder", "field", "outdoors"],
  "caption": "A small red fox kit sits nestled in tall green grass next to a large boulder bordering a tilled agricultural field.",
  "confidence": 0.95
}
```

"Never trusted" is enforced structurally: `app/jobs/matching_job.py` filters
`Image.tag_status != TagStatus.INVALID` *before* the guard ever runs, and
`app/jobs/embedding_job.py` refuses to embed an invalid-tagged image at all
-- an image whose vision output never validated can never become a
suggestion.

### ✅ Low-confidence classifications are flagged instead of accepted

Real confidences from the 50-image run clustered 0.88-1.0. The threshold
(`VISION_CONFIDENCE_THRESHOLD`) was calibrated against that actual
distribution to 0.93 (see `DESIGN.md` "Threshold calibration" /
`BUILDLOG.md`), which flags exactly the identifications the model itself
hedged on:

```
GET /images?tag_status=flagged
[
  {"id": 6,  "category": "fox",  "subject": "gray fox",  "confidence": 0.92},
  {"id": 10, "category": "fox",  "subject": "gray fox",  "confidence": 0.92},
  {"id": 16, "category": "wolf", "subject": "coyote",    "confidence": 0.90},
  {"id": 17, "category": "wolf", "subject": "grey wolf", "confidence": 0.88}
]
```

### ✅ Images are processed through a batch background job with retries

Real job history (`GET /batch/jobs`), including a genuine mid-run failure
and resume (job 1 hit a 20-requests/day quota wall on a preview model
after 18 successes and was resumed as job 2 against a higher-quota model —
see `BUILDLOG.md`):

```
id=1 vision    partial   total=50 completed=18 failed=28
id=2 vision    succeeded total=32 completed=32 failed=0
id=3 embedding partial   total=50 completed=39 failed=11
id=4 embedding succeeded total=11 completed=11 failed=0
```

Per-item retry log excerpt (`app/jobs/runner.py`'s retry loop, real
transient DNS failure, 3 attempts before the item was marked failed and
the batch moved on rather than blocking):

```
WARNING:app.jobs:job=embedding item=44 attempt=1 failed: [Errno -3] Temporary failure in name resolution
WARNING:app.jobs:job=embedding item=44 attempt=2 failed: [Errno -3] Temporary failure in name resolution
WARNING:app.jobs:job=embedding item=44 attempt=3 failed: [Errno -3] Temporary failure in name resolution
```

...and the same image (id 44) resumed successfully once `POST
/images/batch/embed` was called again (endpoint only re-queues images
still missing an embedding — see `app/routers/images.py`).

### ✅ Vision and embedding costs are tracked per call

```
$ curl http://localhost:8000/costs/summary
{
  "rows": [
    {"provider": "gemini", "task_type": "vision",     "calls": 50, "total_units": 70133, "total_cost_usd": 0.0},
    {"provider": "gemini", "task_type": "embedding",  "calls": 63, "total_units": 12915, "total_cost_usd": 0.0}
  ],
  "total_cost_usd": 0.0,
  "total_calls": 113
}
```

113 calls (50 images + 50 image-embeddings + 13 post-embeddings), every
one attributed with a provider/task/units row in `api_call_log`, even
though the free tier keeps `cost_usd` at 0.0.

---

## Matching system

### ✅ Image and post embeddings are stored; posts return ranked image suggestions

```
$ curl http://localhost:8000/posts/1/images
{
  "post": {"id": 1, "title": "The Secret Life of Red Foxes", "expected_category": "fox"},
  "best_match": {
    "id": 1851, "image_id": 9, "rank": 1,
    "similarity_score": 0.8377,
    "status": "accepted",
    "reason": "Category and similarity both clear the bar (similarity 0.84)."
  },
  "suggestions": [ /* 5 accepted (all fox), 44 rejected/no_match, each with a reason */ ]
}
```

### ✅ Semantic matching works for equivalent concepts -- "red fox" matches "Vulpes vulpes"

Post 2's title is literally the Latin binomial: "Vulpes Vulpes:
Understanding the Common Red Fox". Its top-ranked match, computed purely
from embedding similarity (no keyword overlap between "Vulpes Vulpes" and
the image's own tags):

```
best_match: image_id=7, similarity=0.8085, status=accepted
image 7 -> subject: "red fox kit", category: "fox"
```

`app/guard.py: CATEGORY_KEYWORDS["fox"]` also explicitly includes `"vulpes
vulpes"` as a synonym for the category-consistency check layered on top.

---

## Safety layer

### ✅ The mismatch guard rejects incorrect recommendations -- the wolf-on-a-fox-post scenario provably fails

Exact scenario from the brief, live against post 1 ("The Secret Life of
Red Foxes") and every wolf-tagged image in the corpus:

```
image_id=20 sim=0.78 -> REJECTED: "Category mismatch: expected fox, detected wolf."
image_id=11 sim=0.76 -> REJECTED: "Category mismatch: expected fox, detected wolf."
image_id=19 sim=0.75 -> REJECTED: "Category mismatch: expected fox, detected wolf."
image_id=14 sim=0.75 -> REJECTED: "Category mismatch: expected fox, detected wolf."
image_id=13 sim=0.75 -> REJECTED: "Category mismatch: expected fox, detected wolf."
image_id=12 sim=0.75 -> REJECTED: "Category mismatch: expected fox, detected wolf."
image_id=17 sim=0.75 -> REJECTED: "Category mismatch: expected fox, detected wolf."
image_id=18 sim=0.74 -> REJECTED: "Category mismatch: expected fox, detected wolf."
image_id=15 sim=0.72 -> REJECTED: "Category mismatch: expected fox, detected wolf."
```

Every wolf image scored a *higher* raw embedding similarity (0.72-0.78)
than several accepted fox images would need to -- the guard is the only
thing standing between a plausible-looking wrong answer and the user; pure
similarity ranking alone would not have caught this.

Also unit-tested without any DB/API (`tests/test_guard.py::test_guard_rejects_wolf_candidate_on_fox_post`):

```
$ pytest -q tests/test_guard.py
.......                                                                  [100%]
7 passed in 0.05s
```

### ✅ Rejections include a human-readable explanation

Every single one of the 41 rejected candidates on post 1 carries a
specific reason -- category mismatches ("Category mismatch: expected fox,
detected wolf/deer/bear/dog"), unresolvable subjects ("the candidate's
detected subject ('coyote') doesn't resolve to a known category"), and
threshold misses ("Similarity 0.70 is below the 0.71 confidence bar"). No
`reason` field in the entire `suggestions` table is ever empty --
`app/guard.py: evaluate_candidate` returns a reason in every branch.

### ✅ When no image clears the bar, the system answers "no confident match" with reasons

A post about cloud infrastructure costs (no animal content at all) was
run through the full pipeline:

```
$ curl http://localhost:8000/posts/13/images
{
  "post": {"title": "Quarterly Cloud Infrastructure Cost Report", "expected_category": null},
  "best_match": null,
  "suggestions": [
    {
      "image_id": null, "status": "no_match",
      "reason": "No confident match: no candidate cleared both the category check and the 0.71 similarity threshold (best similarity seen was 0.71)."
    },
    /* ...49 individually-reasoned rejections, e.g. "Similarity 0.70 is below the 0.71 confidence bar." */
  ]
}
```

---

## Backend

### ✅ Database models for images, tags, embeddings, posts, suggestions, approvals/rejections -- with the required indexes

`app/models.py` + `alembic/versions/b499e278f357_initial_schema.py`. Real
indexes present in the running database (`sqlalchemy.inspect`):

```
images            -> ix_images_category, ix_images_tag_status
suggestions       -> ix_suggestions_post_id, ix_suggestions_image_id, uq_post_image (unique)
review_decisions  -> ix_review_decisions_suggestion_id (unique)
batch_job_items   -> ix_batch_job_items_batch_job_id
```

### ✅ API endpoints validated; the review workflow (approve / reject / inspect why) exists

```
$ curl http://localhost:8000/review/pending | head -c 200
[{"id": 1851, "post_id": 1, "image_id": 9, "similarity_score": 0.8377, "rank": 1, "status": "accepted", "reason": "..."}, ...]   # 92 pending

$ curl -X POST http://localhost:8000/review/suggestions/1851/decision \
    -H "Content-Type: application/json" \
    -d '{"decision":"approved","note":"Correct fox image, ranked first with high similarity."}'
{"id": 1, "suggestion_id": 1851, "decision": "approved", "note": "...", "created_at": "2026-08-31T16:40:58Z"}

$ curl http://localhost:8000/review/pending | wc  # confirms count dropped 92 -> 91
```

### ✅ Validation at the boundary -- bad input → clean 4xx, never a 500 (shared requirement #2)

```
GET  /images?tag_status=bogus                                -> 422  (was a 500 until this was caught and fixed -- see BUILDLOG.md)
GET  /images?tag_status=valid                                 -> 200
GET  /images/notanumber                                       -> 422
GET  /images/99999                                             -> 404
POST /review/suggestions/1/decision  {"decision":"maybe"}     -> 422
POST /review/suggestions/1/decision  not-json                 -> 422
```

---

## Quality & documentation

### ✅ A small labeled evaluation dataset measures top-1 precision -- the number is in the README

`data/eval_set.json`: 12 hand-labeled posts across the 5 corpus categories
+ 1 deliberate no-match probe post. Real run:

```
$ python -m scripts.run_eval
POST                                          EXPECTED          GOT        OK
-------------------------------------------------------------------------------------
The Secret Life of Red Foxes                  fox               fox        ✓
Vulpes Vulpes: Understanding the Common Red   fox               fox        ✓
Urban Foxes: How Red Foxes Adapt to City Lif  fox               fox        ✓
Why Gray Wolves Are Making a Comeback         wolf              wolf       ✓
Pack Hunters: How Wolves Coordinate in the W  wolf              wolf       ✓
The Howl of the Wolf: Communication in Wolf   wolf              wolf       ✓
The Loyal Companion: A Guide to Dog Breeds    dog               dog        ✓
Training Your New Puppy: The First 30 Days    dog               dog        ✓
Brown Bears and Their Winter Hibernation      bear              bear       ✓
Grizzly Encounters: Staying Safe in Bear Cou  bear              bear       ✓
Red Deer Migration Patterns in Autumn         deer              deer       ✓
The Antlers of the Stag: A Red Deer Life Cyc  deer              deer       ✓
Quarterly Cloud Infrastructure Cost Report    (no-match probe)  NO MATCH   ✓
-------------------------------------------------------------------------------------
Top-1 precision (labeled posts only): 12/12 = 100.00%
```

(Also mirrored in `README.md`'s "Results" section.)

### ✅ README with architecture explanation and diagram; the required files from section 11 present

`README.md` has the architecture diagram + run steps; all of `README.md`,
`capstone.yaml`, `EVIDENCE.md` (this file), `BUILDLOG.md`, `.env.example`,
`DESIGN.md`, and `LICENSE` are present at the repo root.

---

## Full test suite

```
$ pytest -q
...................                                                      [100%]
19 passed in 0.32s
```
