from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models import User
from app.db.session import get_db
from app.services.llm import LLMError
from app.services.qa import answer_question
from app.services.ratelimit import RateLimiter

router = APIRouter(prefix="/ask", tags=["ask"])

user_limiter = RateLimiter(settings.ASK_LIMIT_PER_USER_PER_HOUR)
global_limiter = RateLimiter(settings.ASK_LIMIT_GLOBAL_PER_HOUR)


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    mode: Literal["vector", "keyword", "hybrid", "hybrid_rerank"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=10)
    doc_ids: list[int] | None = None


@router.post("")
def ask(data: AskIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if data.mode == "hybrid_rerank" and not settings.ENABLE_RERANK:
        raise HTTPException(status_code=400, detail="Reranking is disabled on this deployment. Use vector or hybrid.")
    if not global_limiter.allow("global") or not user_limiter.allow(f"user:{user.id}"):
        raise HTTPException(status_code=429, detail="Too many questions right now. Please try again in a few minutes.")
    try:
        return answer_question(db, user.id, data.question, data.mode, data.top_k, data.doc_ids)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))