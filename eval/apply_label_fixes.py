"""Audit ke baad gold labels ka fix. Ye sab modes pe barabar apply hota hai (labels modes se alag hain).

Run (project root se): python -m eval.apply_label_fixes
"""
import json

from eval.common import QUESTIONS_PATH

# Har page ke text me jawab sach me likha hai (audit_failures.txt se verify kiya)
FIXES = {
    "q15": [10, 13, 24, 58],   # p10: helpfulness/safety trade off; p58: tension section
    "q20": [19, 57],           # p19: three annotators (IRR); p57: "Three annotators rate each generation pair"
    "q22": [7, 9, 29],         # p9: Abbreviations list; p29: "country cooperation strategy (CCS)"
    "q26": [42, 43, 48, 49],   # p42-43: whole-of-government / intersectoral actions
    "q29": [6, 30],            # p6: "outlines four strategic priorities"
}


def main() -> None:
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    by_id = {q["id"]: q for q in questions}
    for qid, pages in FIXES.items():
        q = by_id[qid]
        print(f"{qid}: {q['pages']} -> {pages}")
        q["pages"] = pages
    QUESTIONS_PATH.write_text(json.dumps(questions, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {QUESTIONS_PATH}")


if __name__ == "__main__":
    main()