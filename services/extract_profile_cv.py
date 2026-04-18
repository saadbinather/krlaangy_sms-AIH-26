"""Groq LLM JSON extraction for CV text → StudentProfile."""

from __future__ import annotations

import json
import re
from typing import Any, List

from models.schemas import (
    DEGREE_PROGRAM_OPTIONS,
    INTEREST_SUGGESTIONS,
    LOCATION_OPTIONS,
    PREFERRED_OPPORTUNITY_TYPE_OPTIONS,
    SEMESTER_OPTIONS,
    SKILL_SUGGESTIONS,
    StudentProfile,
    WorkExperienceEntry,
)
from services.groq_client import generate_json_text, is_groq_configured


def _allowed_lists_prompt() -> str:
    return f"""
Enumerated fields (must match EXACTLY):

degree_program: {DEGREE_PROGRAM_OPTIONS}
semester: {SEMESTER_OPTIONS}
location_preference: {LOCATION_OPTIONS}
financial_need: ["none", "low", "medium", "high"]

preferred_opportunity_types: choose zero or one from {PREFERRED_OPPORTUNITY_TYPE_OPTIONS} (array of 0 or 1 string)

Free-text list fields (any short strings the CV supports):
- skills: array of strings, e.g. programming languages, tools, soft skills. Use exact wording from CV when possible.
- interests: array of strings (hobbies, domains, anything not in a fixed list).

work_experience: array of objects, each with:
  "job_title": string (required for a row to count)
  "company": string
  "date_started": string (e.g. "Jan 2023" or "2022")
  "date_ended": string (empty if current role)
  "currently_working": boolean

Extract all roles/internships/volunteer jobs that look like employment or structured experience.
If none, use [].

(Suggestions only — not exhaustive: skills may resemble {SKILL_SUGGESTIONS}; interests may resemble {INTEREST_SUGGESTIONS}.)

cgpa: number 0.0–4.5 or null if unknown
graduation_year: integer 1990–2040 or null
"""


_PROFILE_JSON_INSTRUCTIONS = """
You map resume/CV text to a student profile JSON.

Rules:
- Output a single JSON object only. No markdown.
- Use only allowed strings for enumerated fields listed below.
- name: full name from CV header or contact (max 120 chars), or "" if unknown.
- skills and interests: arrays of free-form strings taken from the CV; do not invent items.
- work_experience: LinkedIn-style rows; omit empty rows; set currently_working true when end date says Present/Current/ongoing.

""" + _allowed_lists_prompt() + """
JSON keys (exactly): name, degree_program, semester, cgpa, skills, interests,
preferred_opportunity_types, financial_need, location_preference, work_experience, graduation_year
"""


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _as_str_list(data: dict[str, Any], key: str, *, max_len: int = 160, cap: int = 80) -> List[str]:
    raw = data.get(key)
    if raw is None:
        return []
    if not isinstance(raw, list):
        raw = [raw]
    out: List[str] = []
    for x in raw[:cap]:
        s = str(x).strip()[:max_len]
        if s:
            out.append(s)
    return out


def _as_work_experience(data: dict[str, Any]) -> List[WorkExperienceEntry]:
    raw = data.get("work_experience")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raw = [raw]
    out: List[WorkExperienceEntry] = []
    for item in raw[:30]:
        if not isinstance(item, dict):
            continue
        try:
            out.append(
                WorkExperienceEntry(
                    job_title=str(item.get("job_title", "") or "")[:200],
                    company=str(item.get("company", "") or "")[:200],
                    date_started=str(item.get("date_started", "") or "")[:80],
                    date_ended=str(item.get("date_ended", "") or "")[:80],
                    currently_working=bool(item.get("currently_working", False)),
                )
            )
        except (TypeError, ValueError):
            continue
    return [w for w in out if w.job_title.strip() or w.company.strip()]


def _normalize_profile_dict(data: dict[str, Any]) -> dict[str, Any]:
    data["skills"] = _as_str_list(data, "skills")
    data["interests"] = _as_str_list(data, "interests")
    data["preferred_opportunity_types"] = _as_str_list(
        data, "preferred_opportunity_types", max_len=80, cap=20
    )
    # filter preferred to allowed only
    allowed_pt = set(PREFERRED_OPPORTUNITY_TYPE_OPTIONS)
    data["preferred_opportunity_types"] = [
        x for x in data["preferred_opportunity_types"] if x in allowed_pt
    ]
    # Match UI: single dropdown preference (first listed type wins).
    if len(data["preferred_opportunity_types"]) > 1:
        data["preferred_opportunity_types"] = [data["preferred_opportunity_types"][0]]

    data["work_experience"] = _as_work_experience(data)

    nm = data.get("name")
    data["name"] = str(nm).strip()[:120] if nm is not None else ""

    if data.get("degree_program") not in DEGREE_PROGRAM_OPTIONS:
        data["degree_program"] = "Other / Undeclared"
    if data.get("semester") not in SEMESTER_OPTIONS:
        data["semester"] = "1"
    if data.get("location_preference") not in LOCATION_OPTIONS:
        data["location_preference"] = "Any"
    if data.get("financial_need") not in ("none", "low", "medium", "high"):
        data["financial_need"] = "none"

    gy = data.get("graduation_year")
    if gy is not None:
        try:
            gy = int(gy)
            if gy < 1990 or gy > 2040:
                gy = None
        except (TypeError, ValueError):
            gy = None
    data["graduation_year"] = gy

    cg = data.get("cgpa")
    if cg is not None:
        try:
            cg = float(cg)
            if cg < 0 or cg > 4.5:
                cg = None
        except (TypeError, ValueError):
            cg = None
    data["cgpa"] = cg

    return data


def extract_profile_groq(cv_text: str) -> StudentProfile:
    if not is_groq_configured():
        raise RuntimeError("GROQ_API_KEY not configured")

    prompt = (
        _PROFILE_JSON_INSTRUCTIONS
        + "\n\n--- CV START ---\n"
        + cv_text[:80_000]
        + "\n--- CV END ---\n"
    )
    raw, _model_used = generate_json_text(prompt, context="resume_profile")

    data = json.loads(_strip_json_fence(raw))
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")

    data = _normalize_profile_dict(data)
    return StudentProfile.model_validate(data)


from services.heuristic import extract_profile_with_fallback  # noqa: E402
