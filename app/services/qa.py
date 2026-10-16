import logging
import time

from sqlalchemy.orm import Session

from app.services.llm import chat
from app.services.prompting import (
    NOT_FOUND,
    build_messages,
    build_sources,
    extract_citations,
    snippet_terms,
)
from app.services.retrieval import retrieve

logger = logging.getLogger("docmind.qa")


def answer_question(
    db: Session,
    user_id: int,
    question: str,
    mode: str = "hybrid",
    top_k: int = 5,
    doc_ids: list[int] | None = None,
) -> dict:
    t0 = time.perf_counter()
    chunks = retrieve(db, user_id, question, mode, top_k, doc_ids)

    if not chunks:  # LLM ko bulane ki zarurat hi nahi
        result = {"answer": NOT_FOUND, "sources": [], "cited": False}
    else:
        answer = chat(build_messages(question, chunks))
        cited = extract_citations(answer, len(chunks))
        terms = snippet_terms(question, answer)
        if answer.startswith(NOT_FOUND):
            sources = []
        elif cited:
            sources = build_sources(chunks, cited, terms)
        else:  # LLM ne cite nahi kiya: retrieved chunks dikhao, par flag ke saath
            sources = build_sources(chunks, list(range(1, len(chunks) + 1)), terms)
        result = {"answer": answer, "sources": sources, "cited": bool(cited)}

    result["mode"] = mode
    result["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    logger.info(
        "ask user=%s mode=%s q=%r chunk_ids=%s latency_ms=%s",
        user_id, mode, question[:80], [c["chunk_id"] for c in chunks], result["latency_ms"],
    )
    return result