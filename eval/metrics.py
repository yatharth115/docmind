import math

KS = (1, 3, 5)
QTYPES = ("exact", "paraphrase", "numeric")


def is_hit(result: dict, gold_file: str, gold_pages) -> bool:
    """Result tabhi hit hai jab file bhi wahi ho aur page bhi gold pages me ho."""
    return result.get("filename") == gold_file and result.get("page") in gold_pages


def score_question(results: list[dict], gold_file: str, gold_pages: list[int], ks=KS) -> dict:
    gold = set(gold_pages)
    hits = [is_hit(r, gold_file, gold) for r in results]
    out = {}
    for k in ks:
        found = {r["page"] for r, h in zip(results[:k], hits[:k]) if h}
        out[f"hit@{k}"] = 1.0 if any(hits[:k]) else 0.0
        out[f"recall@{k}"] = len(found) / len(gold)
    rank = next((i for i, h in enumerate(hits, start=1) if h), None)
    out["rr"] = 1.0 / rank if rank else 0.0
    out["first_hit_rank"] = rank
    return out


def mean(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def aggregate(scored: list[dict], ks=KS) -> dict:
    keys = [f"hit@{k}" for k in ks] + [f"recall@{k}" for k in ks]
    out = {k: mean(s[k] for s in scored) for k in keys}
    out["mrr"] = mean(s["rr"] for s in scored)
    return out


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% confidence interval for a proportion (chhote sample ke liye normal se behtar)."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def percentile(values, q: float) -> float:
    """Nearest-rank percentile, q 0-100."""
    xs = sorted(values)
    if not xs:
        return 0.0
    idx = max(0, min(len(xs) - 1, math.ceil(q / 100 * len(xs)) - 1))
    return xs[idx]
