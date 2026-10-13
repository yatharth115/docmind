from fastapi import FastAPI

from app.api import auth, documents

app = FastAPI(title="DocMind")
app.include_router(auth.router)
app.include_router(documents.router)


@app.get("/health")
def health():
    return {"status": "ok"}