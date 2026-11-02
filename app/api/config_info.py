from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["config"])


@router.get("/config")
def public_config():
    """UI ko batata hai ki is deployment me kya allowed hai (koi secret nahi)."""
    return {
        "rerank_enabled": settings.ENABLE_RERANK,
        "registration_enabled": settings.ALLOW_REGISTRATION,
        "read_only": settings.READ_ONLY_DOCS,
    }