import re

NOT_FOUND = "I could not find this in your documents."

SYSTEM_PROMPT = (
    "You are DocMind, a question-answering assistant for the user's own documents. "
    "Answer ONLY from the numbered context chunks provided. "
    "After every claim, cite the chunk number in square brackets, like [1] or [2][3]. "
    f"If the context does not contain the answer, reply exactly: {NOT_FOUND} "
    "You only see a few excerpts, never the whole document. "
    "If the question is very broad or vague (for example 'tell me everything'), say in one sentence "
    "that you only see some excerpts, give a short answer from them, and suggest 2-3 specific "
    "questions the user could ask. Never claim to summarize the whole document. "
    "Never use outside knowledge and never invent facts. "
    "Reply in the same language style as the question."
)

STOPWORDS = {
    "the", "an", "is", "are", "was", "were", "of", "to", "in", "on", "for", "and", "or",
    "what", "which", "how", "do", "does", "it", "this", "that", "with", "as", "by", "at",
    "be", "from", "you", "your", "if", "me", "my", "can", "will", "about", "tell",
}


def _terms(text: str) -> set[str]:
    # 9,500 aur 3.16 jaise tokens tootne nahi chahiye
    found = re.findall(r"\w+(?:[.,\-]\w+)*", text.lower())
    return {t for t in found if t not in STOPWORDS and (len(t) > 1 or t.isdigit())}


def snippet_terms(question: str, answer: str) -> set[str]:
    """Snippet chunne ke liye keywords: sawaal + answer (citation markers [n] hata ke)."""
    return _terms(question + " " + re.sub(r"\[\d+\]", " ", answer))


def best_snippet(text: str, terms: set[str], max_words: int = 45) -> str:
    """Chunk ka wo ~45-word hissa jisme sabse zyada keywords hain (shuru ke 300 chars nahi)."""
    words = text.split()
    if len(words) <= max_words:
        return text[:700]

    hits = [1 if _terms(w) & terms else 0 for w in words]
    window = sum(hits[:max_words])
    best, best_start = window, 0
    for start in range(1, len(words) - max_words + 1):
        window += hits[start + max_words - 1] - hits[start - 1]
        if window > best:
            best, best_start = window, start

    snippet = " ".join(words[best_start:best_start + max_words])
    prefix = "… " if best_start > 0 else ""
    suffix = " …" if best_start + max_words < len(words) else ""
    return (prefix + snippet + suffix)[:700]


def location(chunk: dict) -> str:
    if chunk.get("page") is not None:
        return f"page {chunk['page']}"
    if chunk.get("section"):
        return f"section {chunk['section']}"
    return "unknown location"


def build_messages(question: str, chunks: list[dict]) -> list[dict]:
    blocks = [
        f"[{i}] ({c['filename']}, {location(c)})\n{c['text']}"
        for i, c in enumerate(chunks, start=1)
    ]
    user = "Context:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def extract_citations(answer: str, n_chunks: int) -> list[int]:
    """Answer me se [n] markers nikaalo. Jo number chunks ki range se bahar ho wo hata do."""
    found = {int(m) for m in re.findall(r"\[(\d+)\]", answer)}
    return sorted(n for n in found if 1 <= n <= n_chunks)


def build_sources(chunks: list[dict], cited: list[int], terms: set[str] | None = None) -> list[dict]:
    terms = terms or set()
    return [
        {
            "n": n,
            "chunk_id": chunks[n - 1]["chunk_id"],
            "filename": chunks[n - 1]["filename"],
            "page": chunks[n - 1]["page"],
            "section": chunks[n - 1]["section"],
            "snippet": best_snippet(chunks[n - 1]["text"], terms),
        }
        for n in cited
    ]