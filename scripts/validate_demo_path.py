"""CLI check: fixture emails with Groq on vs UI-disabled.

Run from repo root:
  python scripts/validate_demo_path.py
  python scripts/validate_demo_path.py --no-llm
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from models.schemas import SAMPLE_PROFILE
from app import load_fixture_email_blobs, run_analysis_on_blobs
from services.groq_client import is_groq_configured


def main() -> None:
    no_llm = "--no-llm" in sys.argv

    blobs = load_fixture_email_blobs()
    assert blobs, "fixture empty — add fixtures/sample_emails.txt"
    print("Fixture blobs:", len(blobs))

    print("\n--- LLM disabled in UI (use_llm=False) -> placeholder rows ---")
    results = run_analysis_on_blobs(blobs, SAMPLE_PROFILE.model_copy(), use_llm=False)
    for i, r in enumerate(results, 1):
        opp = r["opportunity"]
        print(
            f"  #{i} tier={r['tier']!r} score={r['score']:.1f} "
            f"src={r.get('extraction_source')} title={opp.title[:70]!r}"
        )

    if no_llm:
        print("\n(--no-llm: skipped live Groq run.)")
        print("\nDone.")
        return

    ok = is_groq_configured()
    print("\n--- Groq configured:", ok, "---")
    if ok:
        print("\n--- Groq extraction (use_llm=True) ---")
        try:
            results2 = run_analysis_on_blobs(
                blobs, SAMPLE_PROFILE.model_copy(), use_llm=True
            )
        except Exception as e:
            print("Run failed:", type(e).__name__, e)
        else:
            for i, r in enumerate(results2, 1):
                opp = r["opportunity"]
                print(
                    f"  #{i} tier={r['tier']!r} score={r['score']:.1f} "
                    f"src={r.get('extraction_source')} title={opp.title[:70]!r}"
                )
    else:
        print("(Set GROQ_API_KEY in .env to validate live Groq extraction.)")

    print("\nDone.")


if __name__ == "__main__":
    main()
