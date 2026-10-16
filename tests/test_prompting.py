from app.services.prompting import (
    best_snippet,
    build_messages,
    build_sources,
    extract_citations,
    location,
    snippet_terms,
)


def test_citations_extracted_sorted_unique():
    assert extract_citations("Mean is average [3]. Median is middle [1][3].", 5) == [1, 3]


def test_out_of_range_citation_dropped():
    assert extract_citations("Made up [7]", 3) == []


def test_no_citation():
    assert extract_citations("No brackets here", 3) == []


def test_location_page_then_section():
    assert location({"page": 4, "section": None}) == "page 4"
    assert location({"page": None, "section": "Intro"}) == "section Intro"


def test_messages_contain_numbered_context_and_question():
    chunks = [{"filename": "a.pdf", "page": 2, "section": None, "text": "hello world", "chunk_id": 9}]
    msgs = build_messages("what?", chunks)
    assert "[1] (a.pdf, page 2)" in msgs[1]["content"]
    assert "Question: what?" in msgs[1]["content"]


def test_build_sources_maps_number_to_chunk():
    chunks = [
        {"filename": "a.pdf", "page": 1, "section": None, "text": "x" * 500, "chunk_id": 10},
        {"filename": "a.pdf", "page": 2, "section": None, "text": "y", "chunk_id": 11},
    ]
    src = build_sources(chunks, [2])
    assert src[0]["chunk_id"] == 11 and src[0]["page"] == 2


def test_best_snippet_finds_answer_part():
    words = ["filler"] * 100 + ["the", "answer", "is", "9,500", "here"] + ["filler"] * 100
    terms = snippet_terms("What is 5% of 10,000 after discount?", "The answer is 9,500 [2]")
    assert "9,500" in best_snippet(" ".join(words), terms)


def test_short_text_returned_whole():
    assert best_snippet("a b c", {"a"}) == "a b c"


def test_snippet_terms_ignore_markers_and_stopwords():
    t = snippet_terms("What is VLOOKUP?", "VLOOKUP searches a value [2]")
    assert "vlookup" in t
    assert "what" not in t
    assert "2" not in t