"""Eval corpus ko disk se seedha DB me daalo (HTTP upload ka 20 MB limit bypass).

Pehli baar:        python -m eval.ingest_corpus
Dobara sab kuch:   python -m eval.ingest_corpus --reset --size 200 --overlap 30
"""
import argparse
import json
import secrets
import sys
import time
from datetime import datetime, timezone

import fitz  # PyMuPDF
from sqlalchemy import func

from app.core.security import hash_password
from app.db.models import Chunk, Document, User
from app.db.session import SessionLocal
from app.services.chunking import chunk_segments
from app.services.embedding import embed_texts
from app.services.parsing import parse_file
from eval.common import CORPUS_DIR, EVAL_EMAIL, META_PATH

BATCH = 64


def get_or_create_user(db) -> User:
    user = db.query(User).filter(User.email == EVAL_EMAIL).first()
    if user is None:
        # random password: is user se login nahi hota, ye sirf eval ke liye hai
        user = User(email=EVAL_EMAIL, hashed_password=hash_password(secrets.token_urlsafe(24)))
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def ingest_pdf(db, user, path, size: int, overlap: int) -> int:
    segments = parse_file(str(path))
    if not segments:
        raise ValueError(f"No text found in {path.name}")
    chunks = chunk_segments(segments, size, overlap)

    # storage_path=None: delete endpoint corpus ki asli file kabhi na mitaye
    doc = Document(user_id=user.id, filename=path.name, status="processing", storage_path=None)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    doc_id = doc.id

    try:
        for i in range(0, len(chunks), BATCH):
            part = chunks[i:i + BATCH]
            vectors = embed_texts([c["text"] for c in part])
            db.add_all([
                Chunk(
                    document_id=doc_id,
                    page=c["page"],
                    section=c["section"],
                    chunk_index=c["chunk_index"],
                    text=c["text"],
                    embedding=v,
                )
                for c, v in zip(part, vectors)
            ])
            db.commit()
            print(f"   {min(i + BATCH, len(chunks))}/{len(chunks)} chunks")
        doc = db.get(Document, doc_id)
        doc.status = "ready"
        db.commit()
    except Exception as e:
        db.rollback()
        doc = db.get(Document, doc_id)
        doc.status = "failed"
        doc.error = str(e)[:500]
        db.commit()
        raise
    return len(chunks)


def write_meta(db, user, size: int, overlap: int) -> None:
    files = {}
    docs = (
        db.query(Document)
        .filter(Document.user_id == user.id, Document.status == "ready")
        .order_by(Document.filename)
        .all()
    )
    for d in docs:
        n_chunks = db.query(func.count(Chunk.id)).filter(Chunk.document_id == d.id).scalar()
        pdf_path = CORPUS_DIR / d.filename
        pages = 0
        if pdf_path.exists():
            with fitz.open(pdf_path) as pdf:
                pages = pdf.page_count
        files[d.filename] = {"pages": pages, "chunks": n_chunks}
    meta = {
        "chunk_size": size,
        "overlap": overlap,
        "ingested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": files,
    }
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    total = sum(f["chunks"] for f in files.values())
    print(f"\nMeta saved to {META_PATH}: {len(files)} files, {total} chunks")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="purane eval docs delete karke sab dobara")
    ap.add_argument("--size", type=int, default=200)
    ap.add_argument("--overlap", type=int, default=30)
    args = ap.parse_args()

    pdfs = sorted(CORPUS_DIR.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No PDFs found in {CORPUS_DIR}")

    size, overlap = args.size, args.overlap
    if not args.reset and META_PATH.exists():
        # corpus me ek hi chunking config rehni chahiye, isliye purani wali use karo
        old = json.loads(META_PATH.read_text(encoding="utf-8"))
        size, overlap = old["chunk_size"], old["overlap"]

    db = SessionLocal()
    try:
        user = get_or_create_user(db)
        if args.reset:
            for d in db.query(Document).filter(Document.user_id == user.id).all():
                db.delete(d)
            db.commit()
            print("Old eval documents deleted.")

        for path in pdfs:
            existing = (
                db.query(Document)
                .filter(Document.user_id == user.id, Document.filename == path.name)
                .first()
            )
            if existing and existing.status == "ready":
                print(f"skip   {path.name} (already ingested)")
                continue
            if existing:  # adhoora ya failed, saaf karke dobara
                db.delete(existing)
                db.commit()

            print(f"ingest {path.name} (chunk size={size}, overlap={overlap})")
            t0 = time.perf_counter()
            n = ingest_pdf(db, user, path, size, overlap)
            print(f"   done: {n} chunks in {time.perf_counter() - t0:.0f}s")

        write_meta(db, user, size, overlap)
    finally:
        db.close()


if __name__ == "__main__":
    main()
