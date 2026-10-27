from eval.metrics import aggregate, percentile, score_question, wilson_interval
from eval.questions import validate_questions


def r(file, page):
    return {"filename": file, "page": page}


def test_hit_at_1_and_mrr():
    s = score_question([r("a.pdf", 5), r("a.pdf", 9)], "a.pdf", [5])
    assert s["hit@1"] == 1.0 and s["rr"] == 1.0 and s["first_hit_rank"] == 1


def test_hit_at_rank_3():
    results = [r("a.pdf", 1), r("a.pdf", 2), r("a.pdf", 5)]
    s = score_question(results, "a.pdf", [5])
    assert s["hit@1"] == 0.0 and s["hit@3"] == 1.0
    assert abs(s["rr"] - 1 / 3) < 1e-9


def test_miss_gives_zero():
    s = score_question([r("a.pdf", 1)], "a.pdf", [5])
    assert s["hit@5"] == 0.0 and s["rr"] == 0.0 and s["first_hit_rank"] is None


def test_same_page_wrong_file_is_not_a_hit():
    s = score_question([r("b.pdf", 5)], "a.pdf", [5])
    assert s["hit@1"] == 0.0


def test_recall_counts_distinct_gold_pages():
    results = [r("a.pdf", 5), r("a.pdf", 5), r("a.pdf", 9)]
    s = score_question(results, "a.pdf", [5, 6])
    assert s["recall@3"] == 0.5


def test_none_page_does_not_crash():
    s = score_question([{"filename": "a.pdf", "page": None}], "a.pdf", [1])
    assert s["hit@1"] == 0.0


def test_aggregate_means():
    scored = [
        score_question([r("a.pdf", 1)], "a.pdf", [1]),
        score_question([r("a.pdf", 2)], "a.pdf", [1]),
    ]
    agg = aggregate(scored)
    assert agg["hit@1"] == 0.5 and agg["mrr"] == 0.5


def test_wilson_interval():
    lo, hi = wilson_interval(8, 10)
    assert 0 <= lo < 0.8 < hi <= 1
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_percentile():
    xs = [10, 20, 30, 40, 50]
    assert percentile(xs, 50) == 30
    assert percentile(xs, 95) == 50
    assert percentile([], 50) == 0.0


def good():
    return {"id": "q01", "question": "What does MEASURE 2.12 cover?", "file": "a.pdf", "pages": [3], "type": "exact"}


def test_valid_questions_pass():
    assert validate_questions([good()], {"a.pdf": 10}) == []


def test_duplicate_id_and_bad_type_and_range():
    bad_type = {**good(), "id": "q02", "type": "weird"}
    out_of_range = {**good(), "id": "q03", "pages": [99]}
    dup = good()
    errors = validate_questions([good(), dup, bad_type, out_of_range], {"a.pdf": 10})
    text = " ".join(errors)
    assert "duplicate id" in text and "type must be" in text and "out of range" in text


def test_unknown_file_and_missing_field():
    unknown = {**good(), "id": "q02", "file": "zzz.pdf"}
    missing = {"id": "q03", "question": "no other fields here"}
    errors = validate_questions([unknown, missing], {"a.pdf": 10})
    text = " ".join(errors)
    assert "unknown file" in text and "missing fields" in text
