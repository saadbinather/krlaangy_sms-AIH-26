"""Groq LLM JSON extraction for opportunity emails → Opportunity (Pydantic)."""

from __future__ import annotations

import json
import re
from typing import Any, Tuple

from models.schemas import Opportunity
from services.groq_client import generate_json_text, is_groq_configured

_OPPORTUNITY_JSON_INSTRUCTIONS = """
You extract structured data from ONE email or message about a scholarship, internship,
fellowship, competition, admission, research position, or similar opportunity.

Rules:
- Output a single JSON object only. No markdown, no commentary.
- Set "is_genuine" to false if the text is spam, a generic newsletter, phishing,
  or clearly NOT an actionable opportunity (e.g. only ads with no real program).
- If is_genuine is false, still provide a short "title" (e.g. "Not an opportunity") and empty lists where unknown.
- Use only information supported by the email; do not invent deadlines or links.
- "deadline": use a short human-readable string, or "TBD" / "Rolling" if not stated.
- "type": one of: Scholarship, Internship, Fellowship, Competition, Admission, Research, Other, Unknown
- "required_skills": skills mentioned as required or preferred (short phrases).
- "opportunity_interests": 2–8 short tags describing the main themes/domains of this opportunity
  (examples: "Artificial Intelligence", "Web development", "Cybersecurity", "Data science", "Robotics").
- "eligibility_conditions": bullet-level eligibility sentences as separate strings.
- "required_documents": documents to submit (transcript, CV, etc.).
- "application_links": full URLs found in the text.
- "contacts": email addresses or phone lines for inquiries.
- "next_steps": 2–5 concrete actions for the student (numbered mentally, as short strings).
- "evidence_quotes": 0–3 short verbatim quotes from the email supporting key facts (deadline, award, requirement).
- "why_it_matters": MUST be a single JSON string (not an array). 2–4 sentences explaining why this opportunity could matter for a student (based on the email).
- "min_cgpa": if the email states a minimum CGPA/GPA requirement, extract a number 0–4.5; else null.

JSON keys (exactly): is_genuine, title, type, deadline, required_skills, opportunity_interests, why_it_matters,
eligibility_conditions, required_documents, application_links, contacts, next_steps, evidence_quotes, min_cgpa
"""


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _coerce_str(v: Any) -> str:
    """LLMs sometimes return a list of sentences; schema expects one string."""
    if v is None:
        return ""
    if isinstance(v, list):
        parts = [str(x).strip() for x in v if str(x).strip()]
        return "\n".join(parts) if parts else ""
    return str(v).strip()


def _normalize_opportunity_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Coerce string fields and list fields so Pydantic validation always succeeds."""
    for key in ("title", "type", "deadline", "why_it_matters"):
        if key in data:
            data[key] = _coerce_str(data.get(key))

    for key in (
        "required_skills",
        "opportunity_interests",
        "eligibility_conditions",
        "required_documents",
        "application_links",
        "contacts",
        "next_steps",
        "evidence_quotes",
    ):
        v = data.get(key)
        if v is None:
            data[key] = []
        elif isinstance(v, list):
            data[key] = [str(x).strip() for x in v if str(x).strip()]
        else:
            data[key] = [str(v).strip()] if str(v).strip() else []

    mg = data.get("min_cgpa")
    if mg is not None and not isinstance(mg, (int, float)):
        try:
            data["min_cgpa"] = float(mg)
        except (TypeError, ValueError):
            data["min_cgpa"] = None

    if "is_genuine" in data and not isinstance(data["is_genuine"], bool):
        data["is_genuine"] = bool(data["is_genuine"])

    return data


def extract_opportunity_groq(email_text: str) -> Opportunity:
    if not is_groq_configured():
        raise RuntimeError("GROQ_API_KEY not configured")

    prompt = (
        _OPPORTUNITY_JSON_INSTRUCTIONS
        + "\n\n--- EMAIL START ---\n"
        + email_text[:120_000]
        + "\n--- EMAIL END ---\n"
    )
    raw, _model_used = generate_json_text(prompt, context="opportunity_email")

    data: Any = json.loads(_strip_json_fence(raw))
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")

    data = _normalize_opportunity_dict(data)
    return Opportunity.model_validate(data)


from services.heuristic import extract_opportunity_with_fallback  # noqa: E402
