"""Seed step (README "run + seed" instructions).

Downloads a small (~50 image, 5 category) licensed-free image corpus from
Wikimedia Commons -- no API key needed, unlike Unsplash/Pexels -- and loads
the hand-labeled blog posts from data/eval_set.json into the database.

Images are *not* committed to the repo (brief section 11: "don't commit
datasets over a few MB"); this script is the reproducible download step
instead, and data/manifest.json (which *is* committed) records exactly what
was downloaded, from where, and under what license.

Usage:
    python -m scripts.seed_corpus
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.models import Image, Post  # noqa: E402

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "flyrank-capstone-image-relevance/1.0 (+https://github.com/PashaAkrilian/Image-Relevance-Auto-Tagging)"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CORPUS_DIR = DATA_DIR / "corpus"
MANIFEST_PATH = DATA_DIR / "manifest.json"
EVAL_SET_PATH = DATA_DIR / "eval_set.json"

# category -> Commons search query. Categories match app/guard.py's CATEGORY_KEYWORDS.
CATEGORIES: dict[str, str] = {
    "fox": "red fox animal wildlife",
    "wolf": "gray wolf animal wildlife",
    "dog": "domestic dog pet",
    "bear": "brown bear animal wildlife",
    "deer": "red deer animal wildlife",
}
IMAGES_PER_CATEGORY = 10


def search_commons_images(query: str, limit: int, client: httpx.Client) -> list[dict]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap",
        "gsrnamespace": 6,  # File: namespace
        "gsrlimit": limit * 4,  # over-fetch, then filter down to real photos
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime|size",
        "iiurlwidth": 800,
    }
    resp = client.get(COMMONS_API, params=params, timeout=30)
    resp.raise_for_status()
    pages = resp.json().get("query", {}).get("pages", {})

    results = []
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        mime = info.get("mime", "")
        if mime not in ("image/jpeg", "image/png"):
            continue
        width = info.get("width") or 0
        if width < 300:
            continue
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue
        extmeta = info.get("extmetadata", {}) or {}
        license_name = extmeta.get("LicenseShortName", {}).get("value", "unknown")
        results.append(
            {
                "title": page.get("title", ""),
                "url": url,
                "license": license_name,
                "source_page": info.get("descriptionurl", ""),
            }
        )
        if len(results) >= limit:
            break
    return results


def download_corpus(client: httpx.Client) -> list[dict]:
    manifest: list[dict] = []
    image_id = 1
    for category, query in CATEGORIES.items():
        cat_dir = CORPUS_DIR / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        print(f"[seed] searching Commons for category={category!r} ...")
        candidates = search_commons_images(query, IMAGES_PER_CATEGORY, client)
        print(f"[seed]   found {len(candidates)} candidates")

        for i, cand in enumerate(candidates, start=1):
            ext = ".jpg" if ".png" not in cand["url"].lower() else ".png"
            file_path = cat_dir / f"{category}_{i:02d}{ext}"
            if not file_path.exists():
                try:
                    r = client.get(cand["url"], timeout=30)
                    r.raise_for_status()
                    file_path.write_bytes(r.content)
                except Exception as exc:  # keep the seed run alive on a single bad URL
                    print(f"[seed]   WARN failed to download {cand['url']}: {exc}")
                    continue
                time.sleep(0.2)  # be polite to Commons

            manifest.append(
                {
                    "id": image_id,
                    "category": category,
                    "file_path": str(file_path.relative_to(DATA_DIR.parent)),
                    "source_url": cand["source_page"] or cand["url"],
                    "license": cand["license"],
                    "title": cand["title"],
                }
            )
            image_id += 1

    return manifest


def load_manifest_into_db(manifest: list[dict]) -> None:
    db = SessionLocal()
    try:
        existing = db.query(Image).count()
        if existing:
            print(f"[seed] {existing} images already in DB, skipping image insert (delete rows to re-seed).")
        else:
            for row in manifest:
                db.add(
                    Image(
                        category=row["category"],
                        file_path=row["file_path"],
                        source_url=row["source_url"],
                        license=row["license"],
                    )
                )
            db.commit()
            print(f"[seed] inserted {len(manifest)} image rows.")

        if db.query(Post).count():
            print("[seed] posts already in DB, skipping.")
        else:
            eval_data = json.loads(EVAL_SET_PATH.read_text())
            for p in eval_data["posts"]:
                db.add(Post(title=p["title"], body=p["body"], expected_category=p["expected_category"]))
            db.commit()
            print(f"[seed] inserted {len(eval_data['posts'])} post rows.")
    finally:
        db.close()


def main() -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        if MANIFEST_PATH.exists() and any(CORPUS_DIR.rglob("*.jpg")):
            print("[seed] corpus already downloaded, reusing existing manifest.json")
            manifest = json.loads(MANIFEST_PATH.read_text())
        else:
            manifest = download_corpus(client)
            MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
            print(f"[seed] wrote {MANIFEST_PATH} ({len(manifest)} images)")

    load_manifest_into_db(manifest)
    print("[seed] done.")


if __name__ == "__main__":
    main()
