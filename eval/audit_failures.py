import argparse
import json
from pathlib import Path

from app.services.parsing import parse_pdf
from app.services.prompting import best_snippet, snippet_terms
from eval.common import CORPUS_DIR, RESULTS_DIR

MAX_PAGES_PER_QUESTION = 6


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(RESULTS_DIR / "results.json"))
    ap.add_argument("--out", default="eval/audit_failures.txt")
    args = ap.parse_args()

    data = json.loads(Path(args.results).read_text(encoding="utf-8"))
    modes = data["meta"]["modes"]

    questions: dict[str, dict] = {}
    for mode in modes:
        for r in data["modes"][mode]["records"]:
            q = questions.setdefault(r["id"], {"rec": r, "missed_by": [], "pages": {}})
            if r["hit@5"]:
                continue
            q["missed_by"].append(mode)
            for t in r["top"]:
                if not t["hit"]:  
                    q["pages"].setdefault((t["file"], t["page"]), set()).add(mode)

    cache: dict[str, dict[int, str]] = {}
    lines: list[str] = []
    missed = {qid: q for qid, q in sorted(questions.items()) if q["missed_by"]}
    for qid, q in missed.items():
        rec = q["rec"]
        lines.append(f"[{qid}] ({rec['type']}) {rec['question']}")
        lines.append(f"  gold: {rec['file']} pages {rec['pages']} | missed by: {', '.join(q['missed_by'])}")
        terms = snippet_terms(rec["question"], "")
        ranked = sorted(q["pages"].items(), key=lambda kv: (-len(kv[1]), kv[0]))
        for (file, page), by in ranked[:MAX_PAGES_PER_QUESTION]:
            if file not in cache:
                segments = parse_pdf(str(CORPUS_DIR / file))
                cache[file] = {s["page"]: s["text"] for s in segments}
            text = cache[file].get(page, "")
            shown = best_snippet(text, terms, max_words=60) if text else "(no text)"
            lines.append(f"  - {file} p.{page} (retrieved by: {', '.join(sorted(by))})")
            lines.append(f"      {shown}")
        lines.append("")

    header = [
        f"{len(missed)} questions were missed by at least one mode (Hit@5).",
        "Rule: add a page to the gold label ONLY if the text below truly answers the question.",
        "Apply the fix for every mode, not just one. Then re-run: python -m eval.run_eval",
        "",
    ]
    Path(args.out).write_text("\n".join(header + lines), encoding="utf-8")
    print(f"{len(missed)} questions need a look. Written to {args.out}")


if __name__ == "__main__":
    main()