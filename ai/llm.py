"""Shared Vertex AI (Gemini) helpers for the enrichment job and the apps.

Auth: Application Default Credentials. Locally that is
`gcloud auth application-default login`; on Cloud Composer it is the
Composer service account (needs roles/aiplatform.user). No API keys.
"""

from __future__ import annotations

import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from google import genai
from google.genai import types

# gemini-2.5-flash-lite was retired on Vertex AI (Oct 2026). Check
# "Model versions and lifecycle" in the Vertex AI docs before changing these.
DEFAULT_CHAT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_CHAT_LOCATION = "global"
DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"
DEFAULT_EMBEDDING_LOCATION = "us-central1"


def env(*names: str, default: str = "") -> str:
    """Return the first non-empty environment variable among names."""
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def project_id() -> str:
    value = env("GASTROFLOW_PROJECT_ID", "GCP_PROJECT_ID")
    if not value:
        raise RuntimeError("Set GASTROFLOW_PROJECT_ID (or GCP_PROJECT_ID).")
    return value


def chat_model() -> str:
    return env("GASTROFLOW_AI_MODEL", default=DEFAULT_CHAT_MODEL)


def embedding_model() -> str:
    return env("GASTROFLOW_EMBEDDING_MODEL", default=DEFAULT_EMBEDDING_MODEL)


def make_chat_client() -> genai.Client:
    location = env("GASTROFLOW_VERTEX_LOCATION", default=DEFAULT_CHAT_LOCATION)
    return genai.Client(vertexai=True, project=project_id(), location=location)


def make_embedding_client() -> genai.Client:
    location = env(
        "GASTROFLOW_EMBEDDING_LOCATION", default=DEFAULT_EMBEDDING_LOCATION
    )
    return genai.Client(vertexai=True, project=project_id(), location=location)


def _sleep_backoff(attempt: int) -> None:
    time.sleep(min(30, 2**attempt) + random.random())


def generate_json(
    client: genai.Client,
    system: str,
    user: str,
    schema: Any,
    *,
    model: str | None = None,
    max_attempts: int = 5,
    max_output_tokens: int = 512,
) -> Any:
    """Call Gemini and return the parsed pydantic object for `schema`."""
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=schema,
        max_output_tokens=max_output_tokens,
    )
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(
                model=model or chat_model(), contents=user, config=config
            )
            if response.parsed is None:
                raise ValueError("Model returned no parseable JSON.")
            return response.parsed
        except Exception as exc:  # network, quota (429), bad JSON...
            last_error = exc
            if attempt < max_attempts:
                _sleep_backoff(attempt)
    raise RuntimeError(
        f"Gemini call failed after {max_attempts} attempts: {last_error}"
    ) from last_error


def generate_text(
    client: genai.Client,
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
    max_attempts: int = 4,
) -> str:
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(
                model=model or chat_model(), contents=user, config=config
            )
            return (response.text or "").strip()
        except Exception as exc:
            last_error = exc
            if attempt < max_attempts:
                _sleep_backoff(attempt)
    raise RuntimeError(
        f"Gemini call failed after {max_attempts} attempts: {last_error}"
    ) from last_error


def embed_texts(
    client: genai.Client,
    texts: list[str],
    *,
    task_type: str = "RETRIEVAL_DOCUMENT",
    model: str | None = None,
    workers: int = 8,
    max_attempts: int = 4,
) -> list[list[float]]:
    """Embed texts one request each (gemini-embedding-001 takes 1 input)."""
    config = types.EmbedContentConfig(task_type=task_type)

    def one(text: str) -> list[float]:
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.models.embed_content(
                    model=model or embedding_model(),
                    contents=text,
                    config=config,
                )
                return list(response.embeddings[0].values)
            except Exception as exc:
                last_error = exc
                if attempt < max_attempts:
                    _sleep_backoff(attempt)
        raise RuntimeError(f"Embedding failed: {last_error}") from last_error

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, texts))
