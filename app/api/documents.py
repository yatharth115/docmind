import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Chunk, Document, User
from app.db.session import SessionLocal, get_db
from app.services.chunking import chunk_segments
from app.services.embedding import embed_texts
from app.services.parsing import parse_file

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = Path("uploads")
ALLOWED_SUFFIXES = {".pdf", ".docx"}
MAX_BYTES = 20 * 1024 * 1024  # 20 MB


def process_document(doc_id: int, path: str) -> None:
    """Background task: parse -> chunk -> embed -> save. Apna alag DB session use karta hai."""
    db = SessionLocal()
    try:
        segments = parse_file(path)
        if not segments:
            raise ValueError("No text found (scanned PDF? OCR is not supported)")
        chunks = chunk_segments(segments)
        vectors = embed_texts([c["text"] for c in chunks])
        db.add_all([
            Chunk(
                document_id=doc_id,
                page=c["page"],
                section=c["section"],
                chunk_index=c["chunk_index"],
                text=c["text"],
                embedding=v,
            )
            for c, v in zip(chunks, vectors)
        ])
        doc = db.get(Document, doc_id)
        doc.status = "ready"
        doc.error = None
        db.commit()
    except Exception as e:
        db.rollback()
        doc = db.get(Document, doc_id)
        if doc:
            doc.status = "failed"
            doc.error = str(e)[:500]
            db.commit()
    finally:
        db.close()


def _owned_doc(db: Session, user: User, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None or doc.user_id != user.id:  # dusre ka doc bhi 404 dikhao
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _out(db: Session, doc: Document) -> dict:
    n_chunks = db.query(func.count(Chunk.id)).filter(Chunk.document_id == doc.id).scalar()
    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "error": doc.error,
        "chunks": n_chunks,
        "created_at": doc.created_at,
    }


@router.post("", status_code=202)
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")

    user_dir = UPLOAD_DIR / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / f"{uuid.uuid4().hex}{suffix}"  # asli filename disk pe nahi, security ke liye
    path.write_bytes(data)

    doc = Document(user_id=user.id, filename=file.filename, status="processing", storage_path=str(path))
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background.add_task(process_document, doc.id, str(path))
    return {"id": doc.id, "filename": doc.filename, "status": doc.status}


@router.get("")
def list_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    docs = (
        db.query(Document)
        .filter(Document.user_id == user.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return [_out(db, d) for d in docs]


@router.get("/{doc_id}")
def get_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _out(db, _owned_doc(db, user, doc_id))


@router.get("/{doc_id}/chunks")
def preview_chunks(
    doc_id: int,
    limit: int = 5,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Debug ke liye: pehle kuch chunks dekho."""
    doc = _owned_doc(db, user, doc_id)
    rows = (
        db.query(Chunk)
        .filter(Chunk.document_id == doc.id)
        .order_by(Chunk.chunk_index)
        .limit(min(limit, 50))
        .all()
    )
    return [
        {"chunk_index": c.chunk_index, "page": c.page, "section": c.section, "text": c.text[:300]}
        for c in rows
    ]


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = _owned_doc(db, user, doc_id)
    if doc.storage_path:
        Path(doc.storage_path).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()