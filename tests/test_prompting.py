from app.services.prompting import build_messages, build_sources, extract_citations, location


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