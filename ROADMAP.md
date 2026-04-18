# SOFTEC-aligned roadmap (closes prior gaps)

This document replaces the gap analysis with a single execution roadmap. It maps every SOFTEC bullet to concrete deliverables in [`app.py`](app.py) and new modules.

## Phase 1 — Data contracts (Pydantic)

**Goal:** Machine-readable inputs/outputs that match the problem statement.

### `StudentProfile` (structured form, no free-text blob for core prefs)

| Field | Type | Notes |
|-------|------|--------|
| `name` | `str` | |
| `degree_program` | `str` | e.g. BS Computer Science |
| `semester` | `int` or `str` | e.g. 6 or "Fall 2025" |
| `cgpa` | `Optional[float]` | For eligibility checks |
| `skills` | `List[str]` | |
| `interests` | `List[str]` | Optional separate from skills |
| `preferred_opportunity_types` | `List[str]` | Enum-like: scholarship, internship, fellowship, competition, admission |
| `financial_need` | `bool` or `Literal["none","low","medium","high"]` | Match brief |
| `location_preference` | `str` | e.g. remote, Lahore, any |
| `past_experience_summary` | `str` | Short |

Persist via `st.session_state`; **Load sample profile** fills all fields.

### `Opportunity` (extraction target for Gemini + fallback heuristic)

| Field | Type | Notes |
|-------|------|--------|
| `is_genuine` | `bool` | Opportunity vs spam / newsletter |
| `title` | `str` | |
| `type` | `str` | Scholarship, Internship, etc. |
| `deadline` | `str` | Raw string; scoring parses date |
| `eligibility_conditions` | `List[str]` | Bullet clauses |
| `required_documents` | `List[str]` | |
| `required_skills` | `List[str]` | |
| `application_links` | `List[str]` | URLs |
| `contacts` | `List[str]` | Emails / phone lines |
| `why_it_matters` | `str` | Narrative for judges |
| `next_steps` | `List[str]` | Ordered actions for the student |
| `evidence_quotes` | `List[str]` | Optional short spans from email proving key facts |

**Files:** New [`models/schemas.py`](models/schemas.py) (or keep in one module initially); [`app.py`](app.py) imports and updates forms.

---

## Phase 2 — Gemini extraction (core AI)

**Goal:** Classification + field extraction from messy English; not “summary only.”

- Add [`services/gemini_client.py`](services/gemini_client.py): configure `google-generativeai`, read `GEMINI_API_KEY` from environment (`.env` + `python-dotenv`).
- Add [`services/extract_opportunity.py`](services/extract_opportunity.py): prompt includes **JSON schema** derived from `Opportunity.model_json_schema()` (or explicit field list). Instructions: extract only what is supported by the email; use empty lists / false for `is_genuine` when not an opportunity.
- Add [`services/extract_profile_from_cv.py`](services/extract_profile_from_cv.py) (optional for demo): CV text → `StudentProfile` with same schema discipline.
- Keep **heuristic extractors** as fallback when API missing or JSON parse fails (log + `st.warning`).

**Dependency:** Add `google-generativeai`, `python-dotenv` to [`requirements.txt`](requirements.txt).

---

## Phase 3 — Deterministic scoring v2

**Goal:** Profile fit + urgency + **completeness**; LLM never assigns rank.

Implement [`services/scoring.py`](services/scoring.py) with a single function e.g. `score_opportunity(opp, profile) -> ScoreResult` where `ScoreResult` contains:

- `total: float` (0–100)
- `tier: Literal["Apply Now","Review","Spam"]`
- `breakdown: dict` — human-readable keys for UI

**Suggested components (tune weights as constants at top of file):**

1. **Fit:** Skill/interest overlap with `required_skills` + optional type match vs `preferred_opportunity_types`.
2. **Eligibility vs profile:** If LLM provides parseable numeric thresholds (e.g. min CGPA in `eligibility_conditions` or a dedicated optional `min_cgpa_hint: Optional[float]` on `Opportunity`), compare to `profile.cgpa`; else skip or small penalty for “unknown eligibility.”
3. **Urgency:** Parsed deadline vs today (reuse / extend current `is_urgent` logic); graduated scale optional.
4. **Completeness (new):** e.g. penalty if no deadline and no rolling indication; bonus if `application_links` non-empty; penalty if `required_documents` empty for genuine opportunities (configurable).
5. **Genuine:** Hard-force Spam tier if `not is_genuine`.

Export **evidence-backed reasons** by merging `breakdown` strings with `opp.evidence_quotes` / `why_it_matters` in the UI only (no extra LLM call).

---

## Phase 4 — Streamlit UI

**Goal:** Full demo flow: structured profile, batch emails, ranked output + checklist.

- **Profile tab/section:** All `StudentProfile` fields via `st.form` (selectboxes/multiselect for types, financial need, location).
- **Inputs:** File upload (txt/csv) **and** `st.text_area` for pasted batch (split same as file rules).
- **Run:** Primary button runs extraction (Gemini or fallback) then scoring, sorts descending.
- **Results table:** Columns — Rank, Title, Type, Deadline, Score, Tier, **Copilot’s logic** (`why_it_matters`), **Next steps** (truncated), key links.
- **Expanders:** Full `next_steps`, `eligibility_conditions`, `required_documents`, deterministic **breakdown** JSON, optional raw snippet.
- **Sample inbox:** Folder [`fixtures/sample_emails/`](fixtures/sample_emails/) with 5–15 English emails; button **Load sample batch** fills the text area or processes files.

**Files:** Refactor [`app.py`](app.py) to thin orchestration; move helpers to `services/`.

---

## Phase 5 — Polish and demo script

- Test all paths: no API key (fallback), bad JSON once, empty paste.
- Ensure 5–15 emails complete in reasonable time (batch calls with small delay if rate-limited).
- README: setup, env var, `streamlit run app.py`, demo order for judges.

---

## Implementation order (strict)

1. Pydantic models + migrate session state / sample profile (`Phase 1`).
2. `scoring.py` v2 against new models (`Phase 3`) — works with heuristic extraction immediately.
3. Gemini extraction + wire `app.py` (`Phase 2`).
4. UI expansion + fixtures + paste (`Phase 4`).
5. README + polish (`Phase 5`).

---

## Traceability to SOFTEC brief

| Brief requirement | Roadmap anchor |
|-------------------|----------------|
| Genuine vs opportunity | `is_genuine` + prompt + Spam tier |
| Deadlines, eligibility, documents, links, contacts | `Opportunity` fields + table/expanders |
| Structured student profile | `StudentProfile` + form |
| Deterministic ranking with evidence | `scoring.py` + breakdown + quotes |
| Action checklist | `next_steps` + UI column/expander |
| 5–15 English emails | `fixtures/` + paste/upload |

This roadmap supersedes the earlier gap-only analysis: following it **eliminates** those gaps by design.
