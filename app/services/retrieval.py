import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.services.embedding import embed_query
from app.services.fusion import rrf_fuse
from app.services.rerank import rerank_scores

CANDIDATES = 20
MODES = ("vector", "keyword", "hybrid", "hybrid_rerank")


def _base(user_id: int, doc_ids: list[int] | None):
    """Sirf us user ke 'ready' documents ke chunks."""
    conds = [Document.user_id == user_id, Document.status == "ready"]
    if doc_ids:
        conds.append(Document.id.in_(doc_ids))
    return select(Chunk.id).join(Document, Document.id == Chunk.document_id).where(*conds)


def vector_search(db: Session, user_id: int, query: str, doc_ids=None, limit: int = CANDIDATES) -> list[int]:
    qvec = embed_query(query)
    stmt = _base(user_id, doc_ids).order_by(Chunk.embedding.cosine_distance(qvec)).limit(limit)
    return list(db.scalars(stmt))


def _tokens(query: str) -> list[str]:
    # 3.16 jaise tokens tootne nahi chahiye, isliye dot/hyphen word ke andar allow
    tokens = re.findall(r"\w+(?:[.\-]\w+)*", query.lower())
    return [t for t in tokens if t != "or"]  # websearch me "or" operator hota hai


def keyword_search(db: Session, user_id: int, query: str, doc_ids=None, limit: int = CANDIDATES) -> list[int]:
    tokens = _tokens(query)
    if not tokens:
        return []
    tsq = func.websearch_to_tsquery("english", " or ".join(tokens))
    stmt = (
        _base(user_id, doc_ids)
        .where(Chunk.tsv.op("@@")(tsq))
        .order_by(func.ts_rank_cd(Chunk.tsv, tsq).desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def _load(db: Session, ids: list[int]) -> dict[int, dict]:
    if not ids:
        return {}
    rows = db.execute(
        select(Chunk, Document.filename)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.id.in_(ids))
    ).all()
    return {
        c.id: {
            "chunk_id": c.id,
            "doc_id": c.document_id,
            "filename": fn,
            "page": c.page,
            "section": c.section,
            "text": c.text,
        }
        for c, fn in rows
    }


def retrieve(
    db: Session,
    user_id: int,
    query: str,
    mode: str = "hybrid_rerank",
    top_k: int = 5,
    doc_ids: list[int] | None = None,
) -> list[dict]:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")

    scores: dict[int, float] = {}
    if mode == "vector":
        ranked = vector_search(db, user_id, query, doc_ids)
    elif mode == "keyword":
        ranked = keyword_search(db, user_id, query, doc_ids)
    else:
        fused = rrf_fuse([
            vector_search(db, user_id, query, doc_ids),
            keyword_search(db, user_id, query, doc_ids),
        ])
        scores = dict(fused)
        ranked = [cid for cid, _ in fused][:CANDIDATES]

    chunks = _load(db, ranked)
    ranked = [cid for cid in ranked if cid in chunks]

    if mode == "hybrid_rerank" and ranked:
        rr = rerank_scores(query, [chunks[cid]["text"] for cid in ranked])
        scores = dict(zip(ranked, rr))
        ranked = sorted(ranked, key=lambda cid: scores[cid], reverse=True)

    results = []
    for cid in ranked[:top_k]:
        item = dict(chunks[cid])
        item["score"] = scores.get(cid)  # vector/keyword me None
        results.append(item)
    return results