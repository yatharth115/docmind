from app.services.retrieval import _tokens


def test_decimal_kept_whole():
    assert _tokens("What is 3.16 LPA?") == ["what", "is", "3.16", "lpa"]


def test_or_removed():
    assert _tokens("cats or dogs") == ["cats", "dogs"]


def test_hyphen_kept():
    assert _tokens("inner-join basics") == ["inner-join", "basics"]