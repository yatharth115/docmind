import time

import requests

from app.core.config import settings


class LLMError(Exception):
    pass


RETRY_STATUS = (429, 500, 502, 503, 504)


def chat(messages: list[dict], temperature: float = 0.1, timeout: int = 60, retries: int = 4) -> str:
    if not settings.LLM_API_KEY:
        raise LLMError("LLM_API_KEY is not set in .env")

    url = settings.LLM_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
    body = {"model": settings.LLM_MODEL, "messages": messages, "temperature": temperature}

    last = "unknown error"
    for attempt in range(retries):
        try:
            r = requests.post(url, json=body, headers=headers, timeout=timeout)
        except requests.RequestException as e:  # timeout / network
            last = str(e)
            time.sleep(2 ** attempt)
            continue

        if r.status_code in RETRY_STATUS:  # rate limit / server error: dobara try
            last = f"{r.status_code}: {r.text[:200]}"
            time.sleep(2 ** attempt)
            continue
        if r.status_code != 200:  # galat key, galat model naam: retry se theek nahi hoga
            raise LLMError(f"LLM error {r.status_code}: {r.text[:300]}")

        try:
            content = r.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError, TypeError):
            raise LLMError("Unexpected LLM response format")
        if not content:  # Gemini kabhi safety filter se khaali jawab deta hai
            raise LLMError("Empty response from model (possibly blocked)")
        return content.strip()

    raise LLMError(f"LLM request failed after {retries} tries: {last}")