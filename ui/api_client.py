import os

import requests

API_URL = os.getenv("DOCMIND_API_URL", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_TIMEOUT = 60


class ApiError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _detail(response) -> str:
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text
    if isinstance(detail, list):  # FastAPI validation errors
        detail = "; ".join(str(d.get("msg", d)) if isinstance(d, dict) else str(d) for d in detail)
    return str(detail)[:300]


def _request(method: str, path: str, token: str | None = None, timeout: int = DEFAULT_TIMEOUT, **kwargs):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = requests.request(method, API_URL + path, headers=headers, timeout=timeout, **kwargs)
    except requests.RequestException as e:
        raise ApiError(f"Cannot reach the DocMind API at {API_URL} ({type(e).__name__}). Is it running?")
    if response.status_code >= 400:
        raise ApiError(_detail(response), response.status_code)
    return response


def register(email: str, password: str) -> dict:
    return _request("POST", "/auth/register", json={"email": email, "password": password}).json()


def login(email: str, password: str) -> str:
    r = _request("POST", "/auth/login", data={"username": email, "password": password})
    return r.json()["access_token"]


def list_documents(token: str) -> list[dict]:
    return _request("GET", "/documents", token).json()


def get_document(token: str, doc_id: int) -> dict:
    return _request("GET", f"/documents/{doc_id}", token).json()


def upload_document(token: str, filename: str, data: bytes) -> dict:
    return _request("POST", "/documents", token, timeout=120, files={"file": (filename, data)}).json()


def delete_document(token: str, doc_id: int) -> None:
    _request("DELETE", f"/documents/{doc_id}", token)


def ask(token: str, question: str, mode: str, top_k: int, doc_ids: list[int] | None = None) -> dict:
    body = {"question": question, "mode": mode, "top_k": top_k, "doc_ids": doc_ids or None}
    return _request("POST", "/ask", token, timeout=120, json=body).json()