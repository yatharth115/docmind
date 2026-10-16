import re

NOT_FOUND = "I could not find this in your documents."

SYSTEM_PROMPT = (
    "You are DocMind, a question-answering assistant for the user's own documents. "
    "Answer ONLY from the numbered context chunks provided. "
    "After every claim, cite the chunk number in square brackets, like [1] or [2][3]. "
    f"If the context does not contain the answer, reply exactly: {NOT_FOUND} "
    "Never use outside knowledge and never invent facts. "
    "Reply in the same language style as the question."
)


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


def build_sources(chunks: list[dict], cited: list[int]) -> list[dict]:
    return [
        {
            "n": n,
            "chunk_id": chunks[n - 1]["chunk_id"],
            "filename": chunks[n - 1]["filename"],
            "page": chunks[n - 1]["page"],
            "section": chunks[n - 1]["section"],
            "snippet": chunks[n - 1]["text"][:300],
        }
        for n in cited
    ]