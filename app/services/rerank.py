from functools import lru_cache

from fastembed.rerank.cross_encoder import TextCrossEncoder

MODEL_NAME = "Xenova/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def _model() -> TextCrossEncoder:
    return TextCrossEncoder(model_name=MODEL_NAME)


def rerank_scores(query: str, texts: list[str]) -> list[float]:
    return [float(s) for s in _model().rerank(query, texts)]