from fastapi import FastAPI

from app.api import ask, auth, documents, search

app = FastAPI(title="DocMind")
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(ask.router)


@app.get("/health")
def health():
    return {"status": "ok"}