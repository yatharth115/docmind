from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.services.retrieval import retrieve

router = APIRouter(prefix="/search", tags=["search"])


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    mode: Literal["vector", "keyword", "hybrid", "hybrid_rerank"] = "hybrid_rerank"
    top_k: int = Field(default=5, ge=1, le=20)
    doc_ids: list[int] | None = None


@router.post("")
def search(data: SearchIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    results = retrieve(db, user.id, data.query, data.mode, data.top_k, data.doc_ids)
    return {"query": data.query, "mode": data.mode, "results": results}