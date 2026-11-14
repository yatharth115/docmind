import json

from eval.common import QUESTIONS_PATH


FIXES = {
    "q15": [10, 13, 24, 58],
    "q20": [19, 57],
    "q22": [7, 9, 29],
    "q26": [42, 43, 48, 49],
    "q29": [6, 30],
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