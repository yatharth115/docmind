MODES = ["vector", "keyword", "hybrid", "hybrid_rerank"]
MODE_LABELS = {
    "vector": "Vector only",
    "keyword": "Keyword only",
    "hybrid": "Hybrid (RRF)",
    "hybrid_rerank": "Hybrid + rerank (most accurate, slower)",
}


def safe_markdown(text: str) -> str:
    """Streamlit '$...$' ko LaTeX samajhta hai (jaise 'US$ 13 million ... US$ 37 million'), isliye escape."""
    return (text or "").replace("$", "\\$")


def location(source: dict) -> str:
    if source.get("page") is not None:
        return f"page {source['page']}"
    if source.get("section"):
        return f"section {source['section']}"
    return "unknown location"


def source_label(source: dict) -> str:
    return f"[{source['n']}] {source['filename']}, {location(source)}"


def status_text(doc: dict) -> str:
    if doc["status"] == "ready":
        return "Ready"
    if doc["status"] == "failed":
        return "Failed"
    return "Processing..."