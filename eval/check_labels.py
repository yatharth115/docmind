"""Har sawaal ke gold page ka sabse relevant hissa dikhata hai, taaki label galat na ho.

Run: python -m eval.check_labels
"""
from app.services.parsing import parse_pdf
from app.services.prompting import best_snippet, snippet_terms
from eval.common import CORPUS_DIR
from eval.questions import load_questions


def main() -> None:
    questions = load_questions()
    cache: dict[str, dict[int, str]] = {}
    for q in questions:
        if q["file"] not in cache:
            segments = parse_pdf(str(CORPUS_DIR / q["file"]))
            cache[q["file"]] = {s["page"]: s["text"] for s in segments}
        pages = cache[q["file"]]
        terms = snippet_terms(q["question"], "")
        print(f"\n[{q['id']}] ({q['type']}) {q['question']}")
        for p in q["pages"]:
            text = pages.get(p)
            shown = best_snippet(text, terms) if text else "(this page has no text!)"
            print(f"   {q['file']} p.{p}: {shown}")


if __name__ == "__main__":
    main()
