from fastapi import FastAPI

from app.api import auth

app = FastAPI(title="DocMind")
app.include_router(auth.router)


@app.get("/health")
def health():
    return {"status": "ok"}