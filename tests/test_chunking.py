from app.services.chunking import chunk_segments, split_words


def test_overlap_and_length():
    text = " ".join(str(i) for i in range(250))
    pieces = split_words(text, size=200, overlap=30)
    assert len(pieces) == 2
    assert pieces[1].split()[0] == "170"      # dusra chunk 170 se shuru
    assert len(pieces[1].split()) == 80


def test_short_text_gives_one_chunk():
    assert len(split_words("a b c")) == 1


def test_empty_text_gives_no_chunks():
    assert split_words("") == []


def test_page_and_index_kept():
    segs = [
        {"page": 1, "section": None, "text": "a " * 10},
        {"page": 2, "section": None, "text": "b " * 10},
    ]
    chunks = chunk_segments(segs)
    assert [c["page"] for c in chunks] == [1, 2]
    assert [c["chunk_index"] for c in chunks] == [0, 1]