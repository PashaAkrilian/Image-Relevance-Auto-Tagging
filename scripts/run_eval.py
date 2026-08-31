"""PROBE 5 / requirement "quality & documentation": measure top-1 precision
against the hand-labeled eval set (data/eval_set.json).

For every post, looks at whichever image the matching engine ranked #1
among *accepted* suggestions (i.e. what actually clears the mismatch
guard) and checks it against the corpus's own ground-truth category label
for that image (not the model's self-reported tag -- we want to know if
the system really recommended the right species, independent of whether
the vision model's own confidence was calibrated).

Usage:
    python -m scripts.run_eval
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.models import Post, Suggestion, SuggestionStatus  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        posts = db.query(Post).order_by(Post.id).all()
        if not posts:
            print("No posts found -- run scripts/seed_corpus.py first.")
            return

        total = 0
        correct = 0
        rows = []
        for post in posts:
            top = (
                db.query(Suggestion)
                .filter(Suggestion.post_id == post.id, Suggestion.status == SuggestionStatus.ACCEPTED, Suggestion.rank == 1)
                .first()
            )
            got_category = top.image.category if (top is not None and top.image is not None) else "NO MATCH"

            if post.expected_category is None:
                # Deliberate no-match probe post (PROBE 4): correct outcome is
                # "NO MATCH", and it's reported separately, not mixed into precision.
                rows.append((post.title, "(no-match probe)", got_category, got_category == "NO MATCH"))
                continue

            total += 1
            is_correct = got_category == post.expected_category
            correct += int(is_correct)
            rows.append((post.title, post.expected_category, got_category, is_correct))

        precision = correct / total if total else 0.0

        print(f"{'POST':45} {'EXPECTED':17} {'GOT':10} {'OK'}")
        print("-" * 87)
        for title, expected, got, ok in rows:
            print(f"{title[:44]:45} {expected or '-':17} {got:10} {'✓' if ok else '✗'}")
        print("-" * 87)
        print(f"Top-1 precision (labeled posts only): {correct}/{total} = {precision:.2%}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
