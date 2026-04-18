"""
Deterministic scoring and tiering. The LLM must never assign rank — only this module does.

**Formula (after eligibility gate), weights sum to 100:**

1. **Interests** (50%) — profile *Interests* text vs opportunity
   (title, type, why_it_matters, skills, eligibility), blended with preferred opportunity type.
2. **Skills** (40%) — resume *Skills* vs ``required_skills`` only.
3. **Deadline** (10%) — urgency only; **last** priority vs fit (interests + skills drive rank).

Tune ``WEIGHT_*_PORTION`` and ``INTEREST_BLEND_*`` below.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Mapping, Optional, Set, Union

from dateutil import parser as date_parser

from models.schemas import Opportunity, StudentProfile

# --- Tunable weights (must sum to 100) ---
# Priority: interests first, then skills, deadline last (tie-breaker / light nudge only).
WEIGHT_INTEREST_PORTION = 50.0
WEIGHT_SKILL_PORTION = 40.0
WEIGHT_DEADLINE_PORTION = 10.0

# How the interest pillar blends (must sum to 1.0)
INTEREST_BLEND_TEXT = 0.45
INTEREST_BLEND_TAGS = 0.40
INTEREST_BLEND_TYPE_PREF = 0.15

URGENCY_DAYS = 7

ProfileLike = Union[StudentProfile, Mapping[str, Any]]

# Tier thresholds (on clamped 0–100 score)
TIER_APPLY_NOW_MIN = 70.0
TIER_REVIEW_MIN = 40.0


TierLabel = Literal["Apply Now", "Review", "Spam"]


@dataclass(frozen=True)
class ScoreResult:
    """Outcome of deterministic scoring for one opportunity + profile."""

    total: float
    tier: TierLabel
    breakdown: Dict[str, object]

    def as_legacy_dict(self) -> dict:
        """Shape expected by existing Streamlit code."""
        return {"score": self.total, "tier": self.tier, "breakdown": self.breakdown}


def _normalize_skill(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _type_keyword(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def _pref_matches_opp_type(prefs: List[str], opp_type: str) -> bool:
    ot = _type_keyword(opp_type)
    for p in prefs:
        pk = _type_keyword(p)
        if len(pk) >= 3 and pk in ot:
            return True
        if len(ot) >= 3 and ot in pk:
            return True
    return False


def _student_profile_like(profile: object) -> bool:
    """
    True for StudentProfile instances, including after Streamlit reload when the class
    object changed but the session still holds an older instance (isinstance fails).
    """
    if isinstance(profile, StudentProfile):
        return True
    return all(
        hasattr(profile, name)
        for name in ("skills", "cgpa", "preferred_opportunity_types")
    )


def _coerce_profile_fields(profile: ProfileLike) -> tuple[List[str], Optional[float], List[str]]:
    """Read skills / cgpa / preferred types from StudentProfile or dict-like."""
    if _student_profile_like(profile):
        p = profile  # StudentProfile or reload-stale instance with same fields
        skills = list(p.skills or [])  # type: ignore[union-attr]
        prefs = list(p.preferred_opportunity_types or [])  # type: ignore[union-attr]
        return (skills, p.cgpa, prefs)  # type: ignore[union-attr]
    raw_skills = profile.get("skills") or []
    if not isinstance(raw_skills, list):
        raw_skills = [raw_skills]
    skills = [str(x) for x in raw_skills]
    cg = profile.get("cgpa")
    cgpa_f: Optional[float]
    try:
        cgpa_f = float(cg) if cg is not None else None
    except (TypeError, ValueError):
        cgpa_f = None
    raw_prefs = profile.get("preferred_opportunity_types") or profile.get("preferred_types") or []
    if not isinstance(raw_prefs, list):
        raw_prefs = [raw_prefs] if raw_prefs else []
    prefs = [str(x) for x in raw_prefs]
    return (skills, cgpa_f, prefs)


def _profile_interests_list(profile: ProfileLike) -> List[str]:
    if _student_profile_like(profile):
        raw_it = getattr(profile, "interests", None) or []
        return [str(x).strip() for x in raw_it if str(x).strip()]
    raw = profile.get("interests") or []
    if not isinstance(raw, list):
        raw = [raw] if raw else []
    return [str(x).strip() for x in raw if str(x).strip()]


def _opp_match_blob(opp: Opportunity) -> str:
    """Lowercased text used to score interest-column fit vs opportunity."""
    parts = [
        opp.title,
        opp.type,
        opp.why_it_matters,
        " ".join(opp.required_skills),
        " ".join(opp.opportunity_interests),
        " ".join(opp.eligibility_conditions),
    ]
    return _normalize_skill(" ".join(parts))


def _interest_text_match_ratio(interests: List[str], blob: str) -> float:
    """
    How well profile **interests** align with opportunity text (0–1).
    If the user left interests empty, return neutral 0.5 (do not punish).
    """
    if not interests:
        return 0.5
    hits = 0
    for intr in interests:
        n = _normalize_skill(intr)
        if len(n) < 2:
            continue
        if n in blob:
            hits += 1
            continue
        matched = False
        for tok in re.findall(r"[a-z0-9]{3,}", n):
            if tok in blob:
                matched = True
                break
        if matched:
            hits += 1
    return hits / len(interests)


def _interest_tag_overlap_ratio(profile_interests: List[str], opp_interest_tags: List[str]) -> float:
    """
    0..1 overlap between profile interests and Groq-extracted opportunity_interests tags.
    If either side is missing, return a neutral midpoint.
    """
    if not profile_interests or not opp_interest_tags:
        return 0.5
    p_norm = {_normalize_skill(x) for x in profile_interests if x.strip()}
    o_norm = {_normalize_skill(x) for x in opp_interest_tags if x.strip()}
    if not p_norm or not o_norm:
        return 0.5
    hits = 0
    for p in p_norm:
        if p in o_norm:
            hits += 1
            continue
        if any(len(tok) >= 3 and tok in o for o in o_norm for tok in re.findall(r"[a-z0-9]{3,}", p)):
            hits += 1
    return hits / max(len(p_norm), 1)


def _type_preference_ratio(prefs: List[str], opp_type: str) -> float:
    """1 = preferred type matches opp; 0.5 = no preference set; 0 = mismatch when prefs exist."""
    if not prefs:
        return 0.5
    return 1.0 if _pref_matches_opp_type(prefs, opp_type) else 0.0


def _interest_fit_ratio(opp: Opportunity, interests: List[str], prefs: List[str]) -> float:
    """
    Single 0–1 blend: mostly **Interests** column vs opportunity text,
    plus preferred opportunity type alignment.
    """
    blob = _opp_match_blob(opp)
    r_text = _interest_text_match_ratio(interests, blob)
    r_tags = _interest_tag_overlap_ratio(interests, opp.opportunity_interests)
    r_type = _type_preference_ratio(prefs, opp.type)
    return (
        INTEREST_BLEND_TEXT * r_text
        + INTEREST_BLEND_TAGS * r_tags
        + INTEREST_BLEND_TYPE_PREF * r_type
    )


def get_days_until(deadline: str) -> Optional[int]:
    """
    Calendar days from now until the parsed deadline (UTC-aware).
    Returns None if deadline is missing or unparseable; negative if already passed.
    """
    if not deadline or deadline.strip().upper() in {"TBD", "ROLLING", "N/A", ""}:
        return None
    try:
        dt = date_parser.parse(deadline, fuzzy=True)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return int((dt - now).total_seconds() // 86400)
    except (ValueError, TypeError, OverflowError):
        return None


def meets_basic_requirements(opp: Opportunity, profile: ProfileLike) -> bool:
    """
    Hard gate: not genuine or CGPA below stated minimum → not eligible (score 0).
    """
    if not opp.is_genuine:
        return False
    _, cgpa_p, _ = _coerce_profile_fields(profile)
    if opp.min_cgpa is not None and cgpa_p is not None and cgpa_p < opp.min_cgpa:
        return False
    return True


def _deadline_fit_ratio(days: Optional[int]) -> float:
    """
    0–1 urgency curve (lowest-weight pillar). More days → lower score;
    unknown / far deadlines still get a small floor.
    """
    if days is None:
        return 0.25
    if days < 0:
        return 0.0
    if days <= URGENCY_DAYS:
        return 1.0
    if days <= 30:
        t = (days - URGENCY_DAYS) / (30 - URGENCY_DAYS)
        return 0.78 * (1.0 - t) + 0.22 * t
    if days <= 90:
        t2 = (days - 30) / 60.0
        return 0.22 * (1.0 - t2) + 0.06 * t2
    return 0.06


def _rank_components(
    opp: Opportunity, profile: ProfileLike
) -> tuple[float, Dict[str, float], Set[str], Optional[int], List[str]]:
    """
    Returns total 0–100, per-component points, matched **resume skill** tokens,
    days_until, and interest strings that matched the opportunity blob.
    """
    if not meets_basic_requirements(opp, profile):
        return (
            0.0,
            {"interests": 0.0, "skills": 0.0, "deadline": 0.0},
            set(),
            None,
            [],
        )

    skills_list, _, prefs = _coerce_profile_fields(profile)
    interests_list = _profile_interests_list(profile)

    blob = _opp_match_blob(opp)
    matched_interest_labels: List[str] = []
    for intr in interests_list:
        n = _normalize_skill(intr)
        if len(n) < 2:
            continue
        if n in blob:
            matched_interest_labels.append(intr)
            continue
        for tok in re.findall(r"[a-z0-9]{3,}", n):
            if tok in blob:
                matched_interest_labels.append(intr)
                break

    r_interest = _interest_fit_ratio(opp, interests_list, prefs)
    interest_points = r_interest * WEIGHT_INTEREST_PORTION

    # Skills: **only** resume/CV skills vs required_skills (not interests)
    req = {_normalize_skill(x) for x in opp.required_skills if x.strip()}
    have_skills = {_normalize_skill(x) for x in skills_list if str(x).strip()}
    common_skills = req & have_skills
    if len(req) == 0:
        skill_ratio = 1.0
    else:
        skill_ratio = len(common_skills) / len(req)
    skill_points = skill_ratio * WEIGHT_SKILL_PORTION

    days = get_days_until(opp.deadline)
    r_deadline = _deadline_fit_ratio(days)
    deadline_points = r_deadline * WEIGHT_DEADLINE_PORTION

    total = interest_points + skill_points + deadline_points
    total = max(0.0, min(100.0, total))
    parts = {
        "interests": interest_points,
        "skills": skill_points,
        "deadline": deadline_points,
    }
    return total, parts, common_skills, days, matched_interest_labels


def rank_opportunity(opp: Opportunity, profile: ProfileLike) -> float:
    """
    Single fit score 0–100 after eligibility:
    interests (50%) + resume skills vs required (40%) + deadline fit (10%, last priority).
    """
    total, _, _, _, _ = _rank_components(opp, profile)
    return total


def is_urgent(deadline: str) -> bool:
    d = get_days_until(deadline)
    return d is not None and 0 <= d <= URGENCY_DAYS


def score_opportunity(opp: Opportunity, profile: StudentProfile) -> ScoreResult:
    """
    Deterministic rank: interests (highest), then skills, deadline last; see module constants.
    """
    total, parts, common_skills, days_left, matched_interests = _rank_components(
        opp, profile
    )

    if not opp.is_genuine:
        tier: TierLabel = "Spam"
        total = 0.0
    elif total >= TIER_APPLY_NOW_MIN:
        tier = "Apply Now"
    elif total >= TIER_REVIEW_MIN:
        tier = "Review"
    else:
        tier = "Review"

    breakdown: Dict[str, object] = {
        f"Interests + type fit (max {WEIGHT_INTEREST_PORTION:g})": round(
            parts["interests"], 1
        ),
        f"Resume skills vs required (max {WEIGHT_SKILL_PORTION:g})": round(
            parts["skills"], 1
        ),
        f"Deadline urgency (max {WEIGHT_DEADLINE_PORTION:g})": round(
            parts["deadline"], 1
        ),
        "Days until deadline": days_left if days_left is not None else "unknown",
        "Matched resume skills": sorted(common_skills),
        "Matched interest keywords": matched_interests,
    }

    return ScoreResult(
        total=round(total, 1),
        tier=tier,
        breakdown=breakdown,
    )


def tier_style(tier: str) -> str:
    """Inline CSS for Streamlit HTML banners."""
    if tier == "Apply Now":
        return "background-color: #e8f5e9; color: #1b5e20;"
    if tier == "Review":
        return "background-color: #fff8e1; color: #f57f17;"
    return "background-color: #eceff1; color: #455a64;"
