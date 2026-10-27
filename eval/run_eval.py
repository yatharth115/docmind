"""4 retrieval modes ko questions.json pe chalao, metrics nikalo, results save karo.

Run: python -m eval.run_eval
     python -m eval.run_eval --out eval/results/chunk100.json
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.db.models import User
from app.db.session import SessionLocal
from app.services.retrieval import MODES, retrieve
from eval.common import EVAL_EMAIL, META_PATH, RESULTS_DIR
from eval.metrics import aggregate, is_hit, percentile, score_question, wilson_interval
from eval.questions import load_questions, validate_questions


def run_mode(db, user_id: int, questions: list[dict], mode: str, top_k: int) -> dict:
    records = []
    for q in questions:
        t0 = time.perf_counter()
        results = retrieve(db, user_id, q["question"], mode, top_k)
        latency_ms = (time.perf_counter() - t0) * 1000
        gold = set(q["pages"])
        records.append({
            "id": q["id"],
            "question": q["question"],
            "type": q["type"],
            "file": q["file"],
            "pages": q["pages"],
            **score_question(results, q["file"], q["pages"]),
            "latency_ms": round(latency_ms, 1),
            "top": [
                {
                    "rank": i,
                    "file": r["filename"],
                    "page": r["page"],
                    "chunk_id": r["chunk_id"],
                    "hit": is_hit(r, q["file"], gold),
                    "text": r["text"][:200],
                }
                for i, r in enumerate(results[:5], start=1)
            ],
        })

    summary = aggregate(records)
    latencies = [r["latency_ms"] for r in records]
    summary["latency_p50_ms"] = percentile(latencies, 50)
    summary["latency_p95_ms"] = percentile(latencies, 95)
    successes = int(sum(r["hit@5"] for r in records))
    return {
        "summary": summary,
        "hit5_ci": wilson_interval(successes, len(records)),
        "records": records,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(RESULTS_DIR / "results.json"))
    ap.add_argument("--top-k", type=int, default=10)
    args = ap.parse_args()

    if not META_PATH.exists():
        sys.exit("Corpus not ingested yet. Run: python -m eval.ingest_corpus")
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    page_counts = {name: f["pages"] for name, f in meta["files"].items()}

    questions = load_questions()
    errors = validate_questions(questions, page_counts)
    if errors:
        print("questions.json has problems:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    types: dict[str, int] = {}
    for q in questions:
        types[q["type"]] = types.get(q["type"], 0) + 1
    print(f"{len(questions)} questions: {types}")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == EVAL_EMAIL).first()
        if user is None:
            sys.exit("Eval user not found. Run: python -m eval.ingest_corpus")

        print("Warming up models (latency me load time na aaye)...")
        for mode in MODES:
            retrieve(db, user.id, "warm up query", mode, 3)

        modes_out = {}
        for mode in MODES:
            print(f"Running {mode} ...")
            modes_out[mode] = run_mode(db, user.id, questions, mode, args.top_k)
    finally:
        db.close()

    payload = {
        "meta": {
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_questions": len(questions),
            "types": types,
            "top_k": args.top_k,
            "chunk_size": meta["chunk_size"],
            "overlap": meta["overlap"],
            "n_chunks": sum(f["chunks"] for f in meta["files"].values()),
            "files": meta["files"],
            "modes": list(MODES),
        },
        "modes": modes_out,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\nSaved {out}\n")
    print(f"{'mode':<16}{'hit@1':>7}{'hit@3':>7}{'hit@5':>7}{'MRR':>7}{'p50 ms':>9}")
    for mode in MODES:
        s = modes_out[mode]["summary"]
        print(
            f"{mode:<16}{s['hit@1']:>7.2f}{s['hit@3']:>7.2f}{s['hit@5']:>7.2f}"
            f"{s['mrr']:>7.2f}{s['latency_p50_ms']:>9.0f}"
        )


if __name__ == "__main__":
    main()
