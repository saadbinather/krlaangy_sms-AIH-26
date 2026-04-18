"""Opportunity Copilot — Streamlit app."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import List, Union

import pandas as pd
import streamlit as st

from models.schemas import (
    DEGREE_PROGRAM_OPTIONS,
    INTEREST_SUGGESTIONS,
    LOCATION_OPTIONS,
    PREFERRED_OPPORTUNITY_TYPE_OPTIONS,
    SAMPLE_PROFILE,
    SEMESTER_OPTIONS,
    SKILL_SUGGESTIONS,
    Opportunity,
    StudentProfile,
    WorkExperienceEntry,
)
from models.text_lists import parse_skills_interests_text

FIXTURE_EMAILS_PATH = Path(__file__).resolve().parent / "fixtures" / "sample_emails.txt"

from services.extract_opportunity import extract_opportunity_with_fallback
from services.extract_profile_cv import extract_profile_with_fallback
from services.groq_client import is_groq_configured
from services.scoring import score_opportunity

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # type: ignore[misc, assignment]

try:
    import docx
except ImportError:
    docx = None  # type: ignore[misc, assignment]


# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');

/* ── Silver theme: readable body text on cool gray ── */
html, body, [class*="css"], .stApp {
    font-family: 'Inter', system-ui, sans-serif !important;
    font-size: 16px !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    background-color: #c5cdd8 !important;
    background-image: linear-gradient(180deg, #d0d7e2 0%, #bfc7d4 100%) !important;
    color: #1e293b !important;
}
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
    color: #1e293b !important;
}
.hero .hero-sub { color: #334155 !important; }
.hero .hero-pill { color: #475569 !important; }
.hero .hero-pill.active { color: #5b21b6 !important; }
.main .block-container { padding-top: 2rem !important; padding-bottom: 4rem !important; }

/* ── Hide chrome ── */
#MainMenu, footer, header { visibility: hidden; }

/* ── Inputs ── */
input, textarea, select,
div[data-baseweb="input"] input,
div[data-baseweb="textarea"] textarea,
div[data-baseweb="select"] {
    background: #f8fafc !important;
    color: #0f172a !important;
    border-color: #94a3b8 !important;
    border-radius: 8px !important;
    font-size: 0.95rem !important;
}
div[data-baseweb="input"] { border-color: #94a3b8 !important; }
div[data-baseweb="select"] > div { background: #f8fafc !important; color: #0f172a !important; }
label { color: #334155 !important; font-size: 0.82rem !important; font-weight: 600 !important; letter-spacing: 0.04em !important; text-transform: uppercase !important; }

/* ── Checkbox ── */
label[data-baseweb="checkbox"] { color: #334155 !important; text-transform: none !important; font-size: 0.95rem !important; letter-spacing: 0 !important; }

/* ── Data editor ── */
.stDataFrame, .dvn-scroller { background: #f1f5f9 !important; color: #0f172a !important; }

/* ── Metrics ── */
div[data-testid="metric-container"] {
    background: #eef2f7;
    border: 1px solid #cbd5e1;
    border-radius: 12px;
    padding: 14px 18px;
}
div[data-testid="metric-container"] label { font-size: 0.75rem !important; color: #475569 !important; }
div[data-testid="metric-container"] div[data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 800 !important; color: #5b21b6 !important; }

/* ── Alerts ── */
div[data-testid="stAlert"] { border-radius: 10px !important; background: #f8fafc !important; border: 1px solid #cbd5e1 !important; color: #334155 !important; }

/* ── Expanders ── */
details { background: #f1f5f9 !important; border: 1px solid #cbd5e1 !important; border-radius: 10px !important; padding: 4px !important; margin-bottom: 6px !important; }
details summary { font-weight: 600 !important; color: #334155 !important; font-size: 0.9rem !important; padding: 8px 12px !important; cursor: pointer !important; letter-spacing: 0.03em !important; }
details summary:hover { color: #5b21b6 !important; }

/* ── Toggle ── */
div[data-testid="stToggle"] label { text-transform: none !important; font-size: 0.95rem !important; letter-spacing: 0 !important; color: #334155 !important; }

/* ── Primary buttons ── */
div.stButton > button[kind="primary"],
div.stFormSubmitButton > button {
    background: linear-gradient(135deg, #6d28d9, #7c3aed) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 9px !important;
    font-weight: 700 !important;
    font-size: 0.92rem !important;
    letter-spacing: 0.03em !important;
    padding: 0.55rem 1.4rem !important;
    transition: all 0.18s ease !important;
    box-shadow: 0 2px 8px rgba(91,33,182,0.25) !important;
}
div.stButton > button[kind="primary"]:hover,
div.stFormSubmitButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(91,33,182,0.35) !important;
}

/* ── Secondary buttons ── */
div.stButton > button[kind="secondary"] {
    background: #f1f5f9 !important;
    color: #334155 !important;
    border: 1px solid #94a3b8 !important;
    border-radius: 9px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    transition: all 0.15s ease !important;
}
div.stButton > button[kind="secondary"]:hover {
    border-color: #6d28d9 !important;
    color: #5b21b6 !important;
    background: #fff !important;
}

/* ── File uploader ── */
section[data-testid="stFileUploadDropzone"] {
    border-radius: 12px !important;
    border: 1.5px dashed #94a3b8 !important;
    background: #e8ecf2 !important;
}
section[data-testid="stFileUploadDropzone"]:hover {
    border-color: #6d28d9 !important;
}
section[data-testid="stFileUploadDropzone"] p,
section[data-testid="stFileUploadDropzone"] span { color: #475569 !important; }

/* ── Divider ── */
hr { border-color: #94a3b8 !important; margin: 36px 0 !important; }

/* ─────────────────────────────────────────────────────────────────────── */
/* CUSTOM COMPONENTS                                                        */
/* ─────────────────────────────────────────────────────────────────────── */

/* ── Hero ── */
.hero {
    position: relative;
    overflow: hidden;
    background: linear-gradient(145deg, #e8ecf2 0%, #dce3ec 100%);
    border: 1px solid #b8c5d6;
    border-radius: 20px;
    padding: 48px 52px 40px;
    margin-bottom: 40px;
    box-shadow: 0 4px 24px rgba(15, 23, 42, 0.06);
}
.hero::before {
    content: '';
    position: absolute;
    top: -80px; right: -80px;
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(91,33,182,0.12) 0%, transparent 70%);
    pointer-events: none;
}
.hero::after {
    content: '';
    position: absolute;
    bottom: -60px; left: 200px;
    width: 300px; height: 300px;
    background: radial-gradient(circle, rgba(59,130,246,0.08) 0%, transparent 70%);
    pointer-events: none;
}
.hero-eyebrow {
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #5b21b6;
    margin-bottom: 14px;
    font-family: 'JetBrains Mono', monospace;
}
.hero-title {
    font-size: 3rem;
    font-weight: 900;
    line-height: 1.08;
    margin: 0 0 16px 0;
    background: linear-gradient(135deg, #0f172a 0%, #4338ca 45%, #6d28d9 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.02em;
}
.hero-sub {
    font-size: 1.05rem;
    color: #334155;
    margin: 0 0 28px 0;
    max-width: 520px;
    line-height: 1.65;
    font-weight: 400;
}
.hero-pills { display: flex; gap: 8px; flex-wrap: wrap; }
.hero-pill {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    padding: 6px 14px;
    border-radius: 999px;
    border: 1px solid #94a3b8;
    color: #475569;
    background: #f8fafc;
}
.hero-pill.active { border-color: #7c3aed; color: #5b21b6; background: rgba(124,58,237,0.1); }

/* ── Section header ── */
.sec-hdr {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #5b21b6;
    font-family: 'JetBrains Mono', monospace;
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 1px solid #94a3b8;
}

/* ── Opportunity card ── */
.opp-card {
    position: relative;
    border-radius: 14px;
    border: 1px solid #cbd5e1;
    padding: 24px 26px;
    margin-bottom: 16px;
    background: #f1f5f9;
    transition: border-color 0.2s, box-shadow 0.2s;
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
}
.opp-card:hover { border-color: #94a3b8; box-shadow: 0 4px 20px rgba(15, 23, 42, 0.08); }
.opp-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 3px; height: 100%;
    border-radius: 14px 0 0 14px;
}
.opp-card.apply::before { background: linear-gradient(180deg, #10b981, #059669); }
.opp-card.review::before { background: linear-gradient(180deg, #a855f7, #7c3aed); }
.opp-card.spam::before { background: #94a3b8; }
.opp-card.apply { border-color: rgba(16,185,129,0.35); }
.opp-card.review { border-color: rgba(124,58,237,0.35); }
.opp-card.spam { opacity: 0.72; }

.opp-rank {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    font-weight: 700;
    color: #64748b;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 5px;
}
.opp-title {
    font-size: 1.2rem;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.35;
    letter-spacing: -0.01em;
}

/* ── Badges ── */
.badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    font-family: 'JetBrains Mono', monospace;
    white-space: nowrap;
}
.badge-apply  { background: rgba(16,185,129,0.15); color: #047857; border: 1px solid rgba(5,150,105,0.45); }
.badge-review { background: rgba(124,58,237,0.12); color: #5b21b6; border: 1px solid rgba(91,33,182,0.35); }
.badge-spam   { background: #e2e8f0; color: #475569; border: 1px solid #94a3b8; }

/* ── Score bar ── */
.score-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.score-num {
    font-size: 1.6rem;
    font-weight: 900;
    color: #0f172a;
    line-height: 1;
    font-family: 'JetBrains Mono', monospace;
}
.score-num span { font-size: 0.9rem; color: #64748b; font-weight: 500; }
.score-bar-bg { height: 6px; border-radius: 999px; background: #cbd5e1; overflow: hidden; margin-top: 8px; }
.bar-apply  { height:100%; border-radius:999px; background: linear-gradient(90deg,#059669,#10b981); }
.bar-review { height:100%; border-radius:999px; background: linear-gradient(90deg,#7c3aed,#a855f7,#c084fc); }
.bar-spam   { height:100%; border-radius:999px; background: #94a3b8; }

/* ── Meta grid ── */
.meta-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px,1fr)); gap: 8px; margin: 16px 0 20px 0; }
.meta-cell { background: #fff; border-radius: 10px; padding: 10px 14px; border: 1px solid #e2e8f0; }
.meta-cell .lbl {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem; color: #64748b; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.08em;
}
.meta-cell .val { font-size: 0.9rem; font-weight: 700; color: #5b21b6; margin-top: 4px; word-break: break-word; }
.meta-cell .val.urgent { color: #dc2626; }

/* ── Why box ── */
.why-box {
    background: rgba(124,58,237,0.06);
    border-left: 3px solid #7c3aed;
    border-radius: 0 8px 8px 0;
    padding: 12px 16px;
    font-size: 0.92rem;
    color: #334155;
    margin: 16px 0;
    line-height: 1.65;
    font-style: italic;
}

/* ── Skill chips ── */
.chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.chip {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 5px;
    font-size: 0.78rem;
    font-weight: 600;
    background: #fff;
    color: #475569;
    border: 1px solid #cbd5e1;
    font-family: 'JetBrains Mono', monospace;
}
.chip-hit {
    background: rgba(16,185,129,0.12);
    color: #047857;
    border-color: rgba(16,185,129,0.35);
}
.chip-none { color: #64748b; font-size: 0.85rem; font-style: italic; }

/* ── Profile snapshot ── */
.snap-box {
    background: #eef2f7;
    border: 1px solid #cbd5e1;
    border-radius: 14px;
    padding: 18px 20px;
    margin-top: 20px;
}
.snap-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #e2e8f0; }
.snap-row:last-child { border-bottom: none; }
.snap-key { font-size: 0.75rem; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; font-family: 'JetBrains Mono', monospace; }
.snap-val { font-size: 0.92rem; font-weight: 600; color: #0f172a; }

/* ── Empty state ── */
.empty-state {
    text-align: center;
    padding: 80px 20px;
    color: #64748b;
}
.empty-state .big { font-size: 3.5rem; margin-bottom: 16px; opacity: 0.45; }
.empty-state .ttl { font-size: 1.05rem; font-weight: 700; color: #475569; letter-spacing: 0.04em; text-transform: uppercase; font-family: 'JetBrains Mono', monospace; }

/* ── Results header ── */
.results-hdr {
    display: flex;
    align-items: baseline;
    gap: 16px;
    margin-bottom: 24px;
}
.results-hdr .big-num {
    font-size: 2.8rem;
    font-weight: 900;
    color: #0f172a;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1;
}
.results-hdr .big-label { font-size: 0.78rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; font-family: 'JetBrains Mono', monospace; }

/* ── Inbox queue badge ── */
.queue-badge {
    display: inline-block;
    background: rgba(124,58,237,0.12);
    border: 1px solid rgba(91,33,182,0.35);
    color: #5b21b6;
    border-radius: 999px;
    padding: 4px 14px;
    font-size: 0.75rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.05em;
    margin-top: 8px;
}
</style>
"""


# ── Ingest helpers ────────────────────────────────────────────────────────────

def _split_email_blobs(raw: str) -> List[str]:
    parts = re.split(r"(?im)^\s*---+\s*EMAIL\s*---+\s*$", raw)
    blobs = [p.strip() for p in parts if p.strip()]
    if len(blobs) <= 1 and "---EMAIL---" not in raw.upper():
        blobs = [b.strip() for b in raw.split("\n\n\n") if b.strip()]
    return blobs if blobs else [raw.strip()]


def extract_text_from_bytes(filename: str, raw_bytes: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        if not PdfReader:
            raise RuntimeError("Install pypdf: pip install pypdf")
        reader = PdfReader(io.BytesIO(raw_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if name.endswith(".docx"):
        if not docx:
            raise RuntimeError("Install python-docx: pip install python-docx")
        d = docx.Document(io.BytesIO(raw_bytes))
        return "\n".join(p.text for p in d.paragraphs)
    return raw_bytes.decode("utf-8", errors="replace")


def parse_emails_upload(uploaded) -> List[str]:
    name = uploaded.name.lower()
    raw_bytes = uploaded.getvalue()
    if name.endswith(".csv"):
        text = raw_bytes.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return []
        body_key = next(
            (k for k in rows[0].keys() if k and k.lower() in ("body", "text", "email", "content", "message")),
            None,
        )
        subj_key = next(
            (k for k in rows[0].keys() if k and k.lower() in ("subject", "title")),
            None,
        )
        out: List[str] = []
        for row in rows:
            sub = (row.get(subj_key, "") if subj_key else "").strip()
            body = (row.get(body_key, "") if body_key else "").strip()
            if not body and not subj_key:
                body = " ".join(str(v) for v in row.values() if v)
            out.append(f"{sub}\n\n{body}".strip() if sub else body)
        return [x for x in out if x]
    if name.endswith(".pdf") or name.endswith(".docx"):
        text = extract_text_from_bytes(name, raw_bytes)
        return _split_email_blobs(text)
    return _split_email_blobs(raw_bytes.decode("utf-8", errors="replace"))


def parse_emails_upload_many(uploaded: Union[None, List[object], object]) -> List[str]:
    if uploaded is None:
        return []
    if isinstance(uploaded, list):
        out: List[str] = []
        for f in uploaded:
            out.extend(parse_emails_upload(f))
        return out
    return parse_emails_upload(uploaded)


def extract_cv_text(uploaded) -> str:
    return extract_text_from_bytes(uploaded.name, uploaded.getvalue())


def run_analysis_on_blobs(blobs: List[str], profile: StudentProfile, *, use_llm: bool) -> List[dict]:
    results = []
    for raw in blobs:
        opp, src = extract_opportunity_with_fallback(raw, use_llm=use_llm)
        pr = score_opportunity(opp, profile).as_legacy_dict()
        results.append(
            {
                "opportunity": opp,
                "score": pr["score"],
                "tier": pr["tier"],
                "breakdown": pr["breakdown"],
                "raw_snippet": raw[:500] + ("…" if len(raw) > 500 else ""),
                "extraction_source": src,
            }
        )
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


# ── Work-experience helpers ───────────────────────────────────────────────────

def _duration_cell(e: WorkExperienceEntry) -> str:
    de = (e.date_ended or "").strip()
    ds = (e.date_started or "").strip()
    if de:
        return f"{ds} – {de}".strip() if ds else de
    return ds


def _work_exp_to_df(entries: List[WorkExperienceEntry]) -> pd.DataFrame:
    if not entries:
        return pd.DataFrame(columns=["employment_type", "company_name", "duration", "currently_working"])
    return pd.DataFrame(
        [{"employment_type": e.job_title, "company_name": e.company,
          "duration": _duration_cell(e), "currently_working": bool(e.currently_working)}
         for e in entries]
    )


def _cell_str(row: object, key: str) -> str:
    v = row[key] if hasattr(row, "__getitem__") else getattr(row, key, "")
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _df_to_work_exp(df: pd.DataFrame) -> List[WorkExperienceEntry]:
    out: List[WorkExperienceEntry] = []
    if df is None or df.empty:
        return out
    for _, row in df.iterrows():
        if "employment_type" in row.index:
            jt = _cell_str(row, "employment_type")
            co = _cell_str(row, "company_name")
            dur = _cell_str(row, "duration")
        else:
            jt = _cell_str(row, "job_title")
            co = _cell_str(row, "company")
            ds = _cell_str(row, "date_started")
            de = _cell_str(row, "date_ended")
            dur = f"{ds} – {de}".strip() if de else ds
        if not jt and not co:
            continue
        cw_raw = row["currently_working"] if "currently_working" in row.index else False
        if cw_raw is None or (isinstance(cw_raw, float) and pd.isna(cw_raw)):
            cw = False
        else:
            cw = bool(cw_raw)
        out.append(WorkExperienceEntry(job_title=jt[:200], company=co[:200],
                                       date_started=dur[:80], date_ended="", currently_working=cw))
    return out


def _preferred_opportunity_select_index(profile: StudentProfile) -> int:
    opts = ["No preference"] + list(PREFERRED_OPPORTUNITY_TYPE_OPTIONS)
    for t in profile.preferred_opportunity_types:
        if t in PREFERRED_OPPORTUNITY_TYPE_OPTIONS:
            try:
                return opts.index(t)
            except ValueError:
                break
    return 0


def _reset_work_exp_editor_if_profile_changed(profile: StudentProfile) -> None:
    pid = id(profile)
    if st.session_state.get("_work_exp_prof_id") != pid:
        st.session_state["_work_exp_prof_id"] = pid
        st.session_state.pop("we_df", None)


def load_fixture_email_blobs() -> List[str]:
    if not FIXTURE_EMAILS_PATH.is_file():
        return []
    raw = FIXTURE_EMAILS_PATH.read_text(encoding="utf-8", errors="replace")
    return _split_email_blobs(raw)


def init_session():
    if "student_profile" not in st.session_state:
        st.session_state.student_profile = StudentProfile()
    if "last_results" not in st.session_state:
        st.session_state.last_results = []
    if "last_cv_extraction" not in st.session_state:
        st.session_state.last_cv_extraction = None
    if "manual_email_blobs" not in st.session_state:
        st.session_state.manual_email_blobs = []


def _format_work_experience(profile: StudentProfile) -> str:
    if not profile.work_experience:
        return "—"
    lines = []
    for w in profile.work_experience:
        dur = _duration_cell(w)
        if w.currently_working and dur:
            dur = f"{dur} (current)"
        elif w.currently_working:
            dur = "current"
        lines.append(f"{w.job_title or '—'} @ {w.company or '—'} — {dur or '—'}")
    return "\n".join(lines)


def _render_cv_extracted_summary(profile: StudentProfile) -> None:
    rows = {
        "Name": profile.name,
        "Degree": profile.degree_program,
        "CGPA": str(profile.cgpa) if profile.cgpa is not None else "—",
        "Semester": profile.semester,
        "Skills": ", ".join(profile.skills) if profile.skills else "—",
        "Interests": ", ".join(profile.interests) if profile.interests else "—",
        "Preferred types": ", ".join(profile.preferred_opportunity_types) or "—",
        "Work experience": _format_work_experience(profile),
    }
    st.table(rows)


# ── Card UI helpers ───────────────────────────────────────────────────────────

def _tier_slug(tier: str) -> str:
    return {"Apply Now": "apply", "Review": "review", "Spam": "spam"}.get(tier, "spam")


def _tier_badge_html(tier: str) -> str:
    labels = {"Apply Now": "APPLY NOW", "Review": "REVIEW", "Spam": "FILTERED"}
    cls    = {"Apply Now": "badge-apply", "Review": "badge-review", "Spam": "badge-spam"}
    return f'<span class="badge {cls.get(tier, "badge-spam")}">{labels.get(tier, tier)}</span>'


def _score_bar_html(score: float, tier: str) -> str:
    slug = _tier_slug(tier)
    pct  = max(0.0, min(100.0, score))
    return (
        f'<div style="display:flex;align-items:center;gap:20px;margin:14px 0 10px 0">'
        f'  <div>'
        f'    <div class="score-label">Match Score</div>'
        f'    <div class="score-num">{score}<span>/100</span></div>'
        f'  </div>'
        f'  <div style="flex:1">'
        f'    <div class="score-bar-bg"><div class="bar-{slug}" style="width:{pct}%"></div></div>'
        f'  </div>'
        f'</div>'
    )


def _meta_cell_html(label: str, value: str, urgent: bool = False) -> str:
    val_cls = "val urgent" if urgent else "val"
    return (
        f'<div class="meta-cell">'
        f'<div class="lbl">{label}</div>'
        f'<div class="{val_cls}">{value}</div>'
        f'</div>'
    )


def _chips_html(opp_skills: List[str], matched: List[str]) -> str:
    if not opp_skills:
        return '<span class="chip-none">open to all</span>'
    matched_set = {s.lower() for s in matched}
    chips = "".join(
        f'<span class="chip {"chip-hit" if s.lower() in matched_set else ""}">{s}</span>'
        for s in opp_skills
    )
    return f'<div class="chip-row">{chips}</div>'


def _deadline_display(deadline: str, days) -> tuple[str, bool]:
    dl = deadline or "TBD"
    if not isinstance(days, int):
        return dl, False
    if days < 0:
        return f"{dl} — expired", False
    if days == 0:
        return f"{dl} — today", True
    if days <= 7:
        return f"{dl} — {days}d left", True
    return f"{dl} — {days}d", False


def _render_opp_card(i: int, row: dict) -> None:
    opp: Opportunity = row["opportunity"]
    tier: str        = row["tier"]
    score: float     = row["score"]
    breakdown: dict  = row["breakdown"]
    slug = _tier_slug(tier)

    days     = breakdown.get("Days until deadline")
    is_past  = isinstance(days, int) and days < 0
    show_next_steps = tier != "Spam" and not is_past

    matched      = breakdown.get("Matched resume skills", [])
    matched_intr = breakdown.get("Matched interest keywords", [])
    if not isinstance(matched, list):
        matched = []
    if not isinstance(matched_intr, list):
        matched_intr = []

    dl_str, dl_urgent = _deadline_display(opp.deadline, days)
    cgpa_str   = str(opp.min_cgpa) if opp.min_cgpa is not None else "—"
    skill_count = f"{len(matched)}/{len(opp.required_skills)}" if opp.required_skills else "open"
    intr_cell   = ", ".join(matched_intr[:4]) + ("…" if len(matched_intr) > 4 else "") or "—"

    card_html = f"""
<div class="opp-card {slug}">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:14px;flex-wrap:wrap">
    <div>
      <div class="opp-rank">RANK {i:02d}</div>
      <div class="opp-title">{opp.title}</div>
    </div>
    {_tier_badge_html(tier)}
  </div>

  {_score_bar_html(score, tier)}

  <div class="meta-grid">
    {_meta_cell_html("Category", opp.type or "—")}
    {_meta_cell_html("Deadline", dl_str, urgent=dl_urgent)}
    {_meta_cell_html("Min CGPA", cgpa_str)}
    {_meta_cell_html("Skills", skill_count)}
    {_meta_cell_html("Interests", intr_cell)}
  </div>

  {"" if tier == "Spam" or not opp.why_it_matters else
    f'<div class="why-box">{opp.why_it_matters}</div>'}

  <div class="score-label" style="margin-bottom:6px">Required Skills</div>
  {_chips_html(opp.required_skills, matched)}
</div>
"""
    st.markdown(card_html, unsafe_allow_html=True)

    if tier != "Spam":
        ec1, ec2 = st.columns(2)
        with ec1:
            with st.expander("Eligibility & documents"):
                if opp.eligibility_conditions:
                    for e in opp.eligibility_conditions:
                        st.markdown(f"- {e}")
                else:
                    st.caption("None stated.")
                if opp.required_documents:
                    st.markdown("**Required documents**")
                    for d in opp.required_documents:
                        st.markdown(f"- {d}")
        with ec2:
            with st.expander("Links & contacts"):
                if opp.application_links:
                    for u in opp.application_links:
                        st.markdown(f"[{u}]({u})")
                else:
                    st.caption("No URLs extracted.")
                if opp.contacts:
                    st.markdown("**Contacts**")
                    for c in opp.contacts:
                        st.markdown(f"`{c}`")

        if show_next_steps and opp.next_steps:
            with st.expander("Action checklist"):
                for j, step in enumerate(opp.next_steps, 1):
                    st.markdown(f"{j}. {step}")

        if opp.evidence_quotes:
            with st.expander("Evidence"):
                for q in opp.evidence_quotes:
                    st.markdown(f"> {q}")

    with st.expander("Score breakdown"):
        st.json(breakdown)

    with st.expander("Raw email snippet"):
        st.caption(f"via **{row.get('extraction_source', '—')}**")
        st.text(row["raw_snippet"])

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Opportunity Copilot",
        page_icon="",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    init_session()
    st.markdown(_CSS, unsafe_allow_html=True)

    _groq_ok    = is_groq_configured()
    use_groq_cv = use_groq_email = _groq_ok

    # ── Hero ─────────────────────────────────────────────────────────────────
    groq_cls = "active" if _groq_ok else ""
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-eyebrow">AI-powered opportunity intelligence</div>
          <div class="hero-title">Opportunity Copilot</div>
          <p class="hero-sub">
            Drop your inbox. Get a ranked shortlist — fit from your skills and
            interests comes first; deadline urgency is only a small part of the score.
          </p>
          <div class="hero-pills">
            <span class="hero-pill active">LLM Extraction</span>
            <span class="hero-pill active">Deterministic Rank</span>
            <span class="hero-pill active">CV Auto-fill</span>
            <span class="hero-pill {groq_cls}">Groq {"Online" if _groq_ok else "Offline"}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Profile + CV ─────────────────────────────────────────────────────────
    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        st.markdown('<div class="sec-hdr">Student Profile</div>', unsafe_allow_html=True)
        p = st.session_state.student_profile

        st.markdown(
            '<div style="font-size:0.82rem;font-weight:600;color:#334155;text-transform:uppercase;'
            'letter-spacing:0.08em;margin-bottom:8px">Work Experience</div>',
            unsafe_allow_html=True,
        )
        _reset_work_exp_editor_if_profile_changed(p)
        edited_work_df = st.data_editor(
            _work_exp_to_df(p.work_experience),
            column_config={
                "employment_type": st.column_config.TextColumn("Role", width="medium"),
                "company_name":    st.column_config.TextColumn("Company", width="medium"),
                "duration":        st.column_config.TextColumn("Duration", width="large"),
                "currently_working": st.column_config.CheckboxColumn("Current", default=False),
            },
            num_rows="dynamic",
            use_container_width=True,
            key="we_df",
            hide_index=True,
        )

        with st.form("profile_form"):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Full name", value=p.name, max_chars=120, placeholder="Your name")
                degree_program = st.selectbox(
                    "Degree", options=DEGREE_PROGRAM_OPTIONS,
                    index=DEGREE_PROGRAM_OPTIONS.index(p.degree_program)
                    if p.degree_program in DEGREE_PROGRAM_OPTIONS else 0)
                semester = st.selectbox(
                    "Semester", options=SEMESTER_OPTIONS,
                    index=SEMESTER_OPTIONS.index(p.semester) if p.semester in SEMESTER_OPTIONS else 0)
            with c2:
                use_cgpa = st.checkbox("Set CGPA", value=p.cgpa is not None)
                cgpa_val_in = st.number_input("CGPA", min_value=0.0, max_value=4.5,
                                               value=float(p.cgpa or 0.0), step=0.01,
                                               disabled=not use_cgpa)
                use_grad = st.checkbox("Set graduation year", value=p.graduation_year is not None)
                grad = st.number_input("Graduation year", min_value=1990, max_value=2040,
                                       value=int(p.graduation_year or 2026), disabled=not use_grad)

            skills_text = st.text_area(
                "Skills", value="\n".join(p.skills) if p.skills else "",
                height=100, placeholder="One per line or comma-separated")
            interests_text = st.text_area(
                "Interests", value="\n".join(p.interests) if p.interests else "",
                height=80, placeholder="Domains, topics, fields you care about")

            _pref_opts = ["No preference"] + list(PREFERRED_OPPORTUNITY_TYPE_OPTIONS)
            _pi = _preferred_opportunity_select_index(p)
            preferred_choice = st.selectbox("Preferred type", options=_pref_opts,
                                            index=min(_pi, len(_pref_opts) - 1))
            preferred_types = [] if preferred_choice == "No preference" else [preferred_choice]

            fc1, fc2 = st.columns(2)
            with fc1:
                financial_need = st.selectbox("Financial need", options=["none","low","medium","high"],
                    index=["none","low","medium","high"].index(p.financial_need))
            with fc2:
                location_preference = st.selectbox(
                    "Location", options=LOCATION_OPTIONS,
                    index=LOCATION_OPTIONS.index(p.location_preference)
                    if p.location_preference in LOCATION_OPTIONS else 0)

            submitted = st.form_submit_button("Save profile", type="primary", use_container_width=True)

        if submitted:
            st.session_state.student_profile = StudentProfile(
                name=(name or "").strip()[:120],
                degree_program=degree_program,  # type: ignore[arg-type]
                semester=semester,  # type: ignore[arg-type]
                cgpa=float(cgpa_val_in) if use_cgpa else None,
                skills=parse_skills_interests_text(skills_text),
                interests=parse_skills_interests_text(interests_text),
                preferred_opportunity_types=preferred_types,
                financial_need=financial_need,  # type: ignore[arg-type]
                location_preference=location_preference,  # type: ignore[arg-type]
                work_experience=_df_to_work_exp(edited_work_df),
                graduation_year=int(grad) if use_grad else None,
            )
            st.success("Saved.")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Load sample", use_container_width=True):
                st.session_state.student_profile = SAMPLE_PROFILE.model_copy()
                st.session_state.last_cv_extraction = None
                st.rerun()
        with b2:
            if st.button("Clear", use_container_width=True):
                st.session_state.student_profile = StudentProfile()
                st.session_state.last_cv_extraction = None
                st.rerun()

    with col_right:
        st.markdown('<div class="sec-hdr">CV Auto-fill</div>', unsafe_allow_html=True)
        cv_file = st.file_uploader("CV upload", type=["pdf", "docx"],
                                   key="cv_file_uploader", label_visibility="collapsed")

        if st.button("Extract profile from CV", key="cv_autofill_btn",
                     type="primary", use_container_width=True):
            if cv_file is None:
                st.warning("Upload a PDF or DOCX first.")
            else:
                with st.spinner("Parsing CV…"):
                    try:
                        text = extract_cv_text(cv_file)
                    except RuntimeError as e:
                        st.error(str(e))
                        text = ""
                    if len(text.strip()) < 15:
                        st.warning("Not enough text in file.")
                    else:
                        new_p, src = extract_profile_with_fallback(text, use_llm=use_groq_cv)
                        st.session_state.student_profile = new_p
                        st.session_state.last_cv_extraction = {"source": src}
                        st.session_state.cv_autofill_success = True
                        st.rerun()

        if st.session_state.pop("cv_autofill_success", False):
            st.success("Done. Review and save.")

        if st.session_state.last_cv_extraction:
            with st.expander("Extracted fields"):
                _render_cv_extracted_summary(st.session_state.student_profile)

        p_snap = st.session_state.student_profile
        if p_snap.name or p_snap.skills:
            snap_rows = []
            if p_snap.name:
                snap_rows.append(("Name", p_snap.name))
            if p_snap.cgpa is not None:
                snap_rows.append(("CGPA", str(p_snap.cgpa)))
            snap_rows.append(("Semester", p_snap.semester))
            snap_rows.append(("Skills", str(len(p_snap.skills))))
            snap_rows.append(("Interests", str(len(p_snap.interests))))
            rows_html = "".join(
                f'<div class="snap-row"><span class="snap-key">{k}</span><span class="snap-val">{v}</span></div>'
                for k, v in snap_rows
            )
            st.markdown(f'<div class="snap-box">{rows_html}</div>', unsafe_allow_html=True)
            if p_snap.skills:
                chips = "".join(f'<span class="chip">{s}</span>' for s in p_snap.skills[:10])
                more  = f'<span class="chip-none">+{len(p_snap.skills)-10} more</span>' if len(p_snap.skills) > 10 else ""
                st.markdown(f'<div class="chip-row" style="margin-top:12px">{chips}{more}</div>',
                            unsafe_allow_html=True)

    # ── Inbox ─────────────────────────────────────────────────────────────────
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="sec-hdr">Opportunity Inbox</div>', unsafe_allow_html=True)

    profile = st.session_state.student_profile
    emails_file = st.file_uploader(
        "Upload emails",
        type=["txt", "csv", "pdf", "docx"],
        accept_multiple_files=True,
        key="emails_file_uploader",
        label_visibility="collapsed",
    )

    pasted_email_text = st.text_area(
        "Paste email text",
        value="",
        height=130,
        placeholder="Paste email text here. Separate multiple emails with ---EMAIL---",
        label_visibility="collapsed",
    )

    c_add, c_clear = st.columns([1, 1])
    with c_add:
        add_manual = st.button("+ Add text", use_container_width=True)
    with c_clear:
        clear_manual = st.button("Clear pasted", use_container_width=True)

    if add_manual:
        new_blobs = _split_email_blobs(pasted_email_text)
        if not pasted_email_text.strip() or not new_blobs:
            st.warning("Nothing to add.")
        else:
            st.session_state.manual_email_blobs.extend(new_blobs)
            st.success(f"{len(new_blobs)} email(s) queued.")
    if clear_manual:
        st.session_state.manual_email_blobs = []
        st.info("Queue cleared.")

    manual_count = len(st.session_state.manual_email_blobs)
    if manual_count:
        st.markdown(
            f'<div class="queue-badge">{manual_count} pasted email{"s" if manual_count != 1 else ""} queued</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    run = st.button("Analyze", type="primary", use_container_width=True)

    if run:
        if not emails_file and not st.session_state.manual_email_blobs:
            st.warning("Upload files or paste email text first.")
        else:
            with st.spinner("Extracting and ranking…"):
                file_blobs: List[str] = []
                if emails_file:
                    try:
                        file_blobs = parse_emails_upload_many(emails_file)
                    except RuntimeError as e:
                        st.error(str(e))

                manual_blobs = list(st.session_state.manual_email_blobs)
                blobs = [*file_blobs, *manual_blobs]
                if not blobs:
                    st.warning("No messages found.")
                else:
                    st.session_state.last_results = run_analysis_on_blobs(
                        blobs, profile, use_llm=use_groq_email
                    )
                    n_files = len(emails_file) if isinstance(emails_file, list) else (1 if emails_file else 0)
                    parts = []
                    if n_files:
                        parts.append(f"{n_files} file(s)")
                    if manual_blobs:
                        parts.append(f"{len(manual_blobs)} pasted")
                    st.success(f"Ranked {len(blobs)} from {' + '.join(parts)}.")

    # ── Results ───────────────────────────────────────────────────────────────
    if st.session_state.last_results:
        results  = st.session_state.last_results
        apply_n  = sum(1 for r in results if r["tier"] == "Apply Now")
        review_n = sum(1 for r in results if r["tier"] == "Review")
        spam_n   = sum(1 for r in results if r["tier"] == "Spam")

        st.markdown("<hr>", unsafe_allow_html=True)

        st.markdown(
            f"""
            <div class="results-hdr">
              <div>
                <div class="big-num">{len(results)}</div>
                <div class="big-label">opportunities ranked</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Apply Now", apply_n)
        mc2.metric("Review",    review_n)
        mc3.metric("Filtered",  spam_n)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        show_spam = st.toggle("Show filtered / expired", value=False)

        visible = [r for r in results if show_spam or r["tier"] != "Spam"]
        if not visible:
            st.info("Nothing to show. Toggle filtered items above.")
        else:
            for i, row in enumerate(visible, start=1):
                _render_opp_card(i, row)
    else:
        st.markdown(
            """
            <div class="empty-state">
              <div class="big">—</div>
              <div class="ttl">No results yet</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
