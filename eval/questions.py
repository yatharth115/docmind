import json
from pathlib import Path

from eval.common import QUESTIONS_PATH
from eval.metrics import QTYPES

REQUIRED = ("id", "question", "file", "pages", "type")


def load_questions(path=QUESTIONS_PATH) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_questions(questions: list, page_counts: dict[str, int]) -> list[str]:
    """Galtiyon ki list lautata hai. Khaali list = sab theek."""
    errors: list[str] = []
    if not isinstance(questions, list) or not questions:
        return ["questions.json must be a non-empty list"]

    seen: set[str] = set()
    for i, q in enumerate(questions, start=1):
        if not isinstance(q, dict):
            errors.append(f"#{i}: must be an object")
            continue
        qid = str(q.get("id", f"#{i}"))
        missing = [k for k in REQUIRED if k not in q]
        if missing:
            errors.append(f"{qid}: missing fields {missing}")
            continue
        if qid in seen:
            errors.append(f"{qid}: duplicate id")
        seen.add(qid)
        if not isinstance(q["question"], str) or len(q["question"].strip()) < 10:
            errors.append(f"{qid}: question text too short")
        if q["type"] not in QTYPES:
            errors.append(f"{qid}: type must be one of {QTYPES}")
        if q["file"] not in page_counts:
            errors.append(f"{qid}: unknown file {q['file']!r} (known: {sorted(page_counts)})")
            continue
        pages = q["pages"]
        if not isinstance(pages, list) or not pages or not all(isinstance(p, int) for p in pages):
            errors.append(f"{qid}: pages must be a non-empty list of integers")
            continue
        if len(set(pages)) != len(pages):
            errors.append(f"{qid}: duplicate pages")
        n = page_counts[q["file"]]
        for p in pages:
            if p < 1 or p > n:
                errors.append(f"{qid}: page {p} out of range (1-{n}) for {q['file']}")
    return errors
