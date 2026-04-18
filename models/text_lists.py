"""Parse free-text lines / comma-separated values into deduplicated string lists."""

from __future__ import annotations

import re
from typing import List


def parse_skills_interests_text(text: str) -> List[str]:
    """Split on newlines, commas, or semicolons; trim; drop empties; preserve order, dedupe."""
    if not text or not str(text).strip():
        return []
    parts: List[str] = []
    for chunk in re.split(r"[\n,;]+", str(text)):
        s = chunk.strip()
        if s:
            parts.append(s)
    seen: set[str] = set()
    out: List[str] = []
    for p in parts:
        key = p.casefold()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out
