
import random
import time

import requests

from app.core.config import settings


class LLMError(Exception):
    pass


class RetryableLLMError(LLMError):
    pass


RETRY_STATUS = (429, 500, 502, 503, 504)


def _request_model(
    model: str,
    messages: list[dict],
    temperature: float,
    timeout: int,
    retries: int,
) -> str:
    url = settings.LLM_BASE_URL.rstrip("/") + "/chat/completions"

    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    last_error = "unknown error"
    attempts = max(1, retries)
    start_time = time.time()
    print(f"[LLM] Trying model: {model}", flush=True)

    for attempt in range(attempts):
        try:
            response = requests.post(
                url,
                json=body,
                headers=headers,
                timeout=(15, timeout),
            )

        except requests.RequestException as e:
            last_error = str(e)

        else:
            if response.status_code in RETRY_STATUS:
                last_error = (
                    f"HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                )

            elif response.status_code != 200:
                raise LLMError(
                    f"Model {model} returned "
                    f"HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                )

            else:
                try:
                    content = response.json()["choices"][0]["message"]["content"]
                except (KeyError, IndexError, ValueError, TypeError):
                    raise LLMError(
                        f"Unexpected response format from {model}"
                    )

                if not isinstance(content, str) or not content.strip():
                    raise LLMError(
                        f"Empty response from model {model}"
                    )
                print(
                    f"[LLM] {model} succeeded in "
                    f"{time.time() - start_time:.2f} seconds",
                    flush=True,
                )
                return content.strip()

        if attempt < attempts - 1:
            delay = min(2 ** attempt, 8) + random.uniform(0, 0.5)
            print(
                f"[LLM] {model} attempt {attempt + 1} failed: {last_error}",
                flush=True,
            )
            time.sleep(delay)

    raise RetryableLLMError(
        f"Model {model} failed after {attempts} attempts: {last_error}"
    )


def chat(
    messages: list[dict],
    temperature: float = 0.1,
    timeout: int = 60,
    retries: int = 2,
) -> str:

    if not settings.LLM_API_KEY:
        raise LLMError("LLM_API_KEY is not set in .env")

    primary = settings.LLM_MODEL
    fallback = settings.LLM_FALLBACK_MODEL

    models = [primary]

    if fallback and fallback != primary:
        models.append(fallback)

    errors = []

    for model in models:
        try:
            model_timeout = 15 if model == primary else 45
            model_retries = 1 if model == primary else 2

            return _request_model(
                model=model,
                messages=messages,
                temperature=temperature,
                timeout=model_timeout,
                retries=model_retries,
            )

        except RetryableLLMError as e:
            errors.append(str(e))

    raise LLMError(
        "All configured LLM models failed. "
        + " | ".join(errors)
    )
