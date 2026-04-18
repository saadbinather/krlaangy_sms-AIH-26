"""
LLM (Groq) extraction orchestration — no rule-based fallbacks.

Loads ``.env`` from the project root. Prompts live in
``extract_opportunity.py`` and ``extract_profile_cv.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from models.schemas import Opportunity, StudentProfile


def _truncate_err(msg: str, max_len: int = 280) -> str:
    msg = (msg or "").strip().replace("\n", " ")
    return msg if len(msg) <= max_len else msg[: max_len - 1] + "…"


def _opportunity_no_api_key() -> Opportunity:
    return Opportunity(
        is_genuine=False,
        title="GROQ_API_KEY not configured",
        type="Unknown",
        deadline="TBD",
        why_it_matters=(
            "Add **GROQ_API_KEY** to the project `.env` file (get a key at "
            "https://console.groq.com/keys), then restart Streamlit."
        ),
        next_steps=[
            "Open `.env` in the project folder",
            "Set GROQ_API_KEY=gsk_...",
            "Restart the app",
        ],
    )


def _opportunity_llm_disabled() -> Opportunity:
    return Opportunity(
        is_genuine=False,
        title="Groq extraction is turned off",
        type="Unknown",
        deadline="TBD",
        why_it_matters=(
            "Turn on **Use Groq for email extraction** in the sidebar, or add "
            "your API key if the checkbox is disabled."
        ),
        next_steps=["Enable the Groq checkbox in the sidebar", "Re-run analysis"],
    )


def _opportunity_llm_failed(err: str) -> Opportunity:
    return Opportunity(
        is_genuine=False,
        title="Groq extraction failed",
        type="Unknown",
        deadline="TBD",
        why_it_matters=(
            "The model could not return valid JSON. Details: "
            f"{_truncate_err(err)}. Check **GROQ_MODEL**, quota, and network."
        ),
        next_steps=[
            "Verify GROQ_API_KEY at console.groq.com",
            "Try `GROQ_MODEL=llama-3.3-70b-versatile` in `.env`",
        ],
    )


def _profile_no_api_key() -> StudentProfile:
    return StudentProfile(
        name="",
        degree_program="Other / Undeclared",
        semester="1",
    )


def _profile_llm_disabled() -> StudentProfile:
    return StudentProfile(
        name="",
        degree_program="Other / Undeclared",
        semester="1",
    )


def _profile_llm_failed(_err: str) -> StudentProfile:
    return StudentProfile(
        name="",
        degree_program="Other / Undeclared",
        semester="1",
    )


def extract_opportunity_with_fallback(
    email_text: str, *, use_llm: bool = True
) -> Tuple[Opportunity, str]:
    """
    Extract using **Groq** only.

    Returns (opportunity, source): ``groq`` | ``no_api_key`` | ``llm_disabled`` | ``groq_failed``.
    """
    from services.groq_client import is_groq_configured
    from services.extract_opportunity import extract_opportunity_groq

    if not is_groq_configured():
        return _opportunity_no_api_key(), "no_api_key"
    if not use_llm:
        return _opportunity_llm_disabled(), "llm_disabled"
    try:
        return extract_opportunity_groq(email_text), "groq"
    except Exception as e:
        return _opportunity_llm_failed(repr(e)), "groq_failed"


def extract_profile_with_fallback(
    cv_text: str, *, use_llm: bool = True
) -> Tuple[StudentProfile, str]:
    """CV → profile using **Groq** only."""
    from services.groq_client import is_groq_configured
    from services.extract_profile_cv import extract_profile_groq

    if not is_groq_configured():
        return _profile_no_api_key(), "no_api_key"
    if not use_llm:
        return _profile_llm_disabled(), "llm_disabled"
    try:
        return extract_profile_groq(cv_text), "groq"
    except Exception as e:
        return _profile_llm_failed(repr(e)), "groq_failed"
