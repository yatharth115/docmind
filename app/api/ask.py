from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.services.llm import LLMError
from app.services.qa import answer_question

router = APIRouter(prefix="/ask", tags=["ask"])


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    mode: Literal["vector", "keyword", "hybrid", "hybrid_rerank"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=10)
    doc_ids: list[int] | None = None


@router.post("")
def ask(data: AskIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return answer_question(db, user.id, data.question, data.mode, data.top_k, data.doc_ids)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))