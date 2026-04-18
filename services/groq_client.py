"""Groq OpenAI-compatible API for JSON extraction."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Default: strong JSON instruction-following. Override with GROQ_MODEL in .env
DEFAULT_MODEL = "llama-3.3-70b-versatile"

_MODEL_FALLBACKS: List[str] = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    except ImportError:
        pass


def get_api_key() -> str:
    _load_dotenv()
    return (os.getenv("GROQ_API_KEY") or "").strip()


def is_groq_configured() -> bool:
    return bool(get_api_key())


def get_model_name() -> str:
    _load_dotenv()
    raw = (os.getenv("GROQ_MODEL") or "").strip()
    return raw if raw else DEFAULT_MODEL


def iter_model_names_to_try() -> List[str]:
    _load_dotenv()
    explicit = (os.getenv("GROQ_MODEL") or "").strip()
    out: List[str] = []
    if explicit:
        out.append(explicit)
    for m in _MODEL_FALLBACKS:
        if m not in out:
            out.append(m)
    return out


def get_sidebar_model_hint() -> str:
    _load_dotenv()
    if (os.getenv("GROQ_MODEL") or "").strip():
        return f"`{get_model_name()}` (+ fallbacks if needed)"
    return f"`{DEFAULT_MODEL}` then `{_MODEL_FALLBACKS[1]}`"


def generate_json_text(prompt: str, *, context: str = "groq") -> Tuple[str, str]:
    """
    Call Groq chat completions; prefer JSON object mode when supported.

    Args:
        prompt: User message sent to the model.
        context: Short label for logs (e.g. ``resume_profile``, ``opportunity_email``).

    Returns:
        (raw_text, model_id_used)
    """
    if not is_groq_configured():
        raise RuntimeError("GROQ_API_KEY not configured")

    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("Install openai: pip install openai") from e

    client = OpenAI(api_key=get_api_key(), base_url=GROQ_BASE_URL)

    system_msg = (
        "You extract structured data. Reply with a single valid JSON object only, "
        "no markdown fences, no commentary."
    )

    last_err: Exception | None = None
    for model in iter_model_names_to_try():
        try:
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.15,
                    response_format={"type": "json_object"},
                )
            except Exception:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.15,
                )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                preview = text[:500] + ("…" if len(text) > 500 else "")
                print(
                    f"[Groq] OK context={context!r} model={model} chars={len(text)} "
                    f"preview={preview!r}"
                )
                return text, model
            last_err = ValueError(f"Empty content from model {model!r}")
        except Exception as e:
            last_err = e
            continue

    msg = f"Groq JSON generation failed after {len(iter_model_names_to_try())} model(s)."
    if last_err is not None:
        msg += f" Last error: {last_err}"
    logger.warning("Groq failed context=%s: %s", context, msg)
    print(f"[Groq] FAIL context={context!r} {msg}")
    raise RuntimeError(msg)
