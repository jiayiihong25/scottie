"""Heuristic conceptual/memorization tagging.

Deterministic and inspectable on purpose — same principle as `pacing/`:
get a simple, debuggable version working before reaching for anything
model-based. `score` is the fraction of matched signal that pointed at
memorization; `CLASSIFY_MARGIN` controls how decisive that has to be
before we tag it instead of defaulting to conceptual.
"""

from __future__ import annotations

import re

CONCEPTUAL = "conceptual"
MEMORIZATION = "memorization"

# A tie, or anything close to it, defaults to conceptual: a false negative
# here just means a fact gets a concept-check question instead of a
# flashcard, which is a much smaller loss than the reverse (definitions
# gone missing from Anki review).
CLASSIFY_MARGIN = 0.15

_MEMORIZATION_PATTERNS = [
    re.compile(r"\bis defined as\b", re.IGNORECASE),
    re.compile(r"\brefers to\b", re.IGNORECASE),
    re.compile(r"\bknown as\b", re.IGNORECASE),
    re.compile(r"^\s*[A-Za-z0-9 '/-]{1,60}:\s+\S"),  # "Term: definition" lines
    re.compile(r"\b\d{3,4}\s*(BCE|BC|CE|AD)\b"),
    re.compile(r"\bequation\b|\bformula\b", re.IGNORECASE),
    re.compile(r"^\s*[-*•]\s+\S"),  # bullet list of discrete facts
    re.compile(r"\b(vocabulary|glossary|terminology)\b", re.IGNORECASE),
]

_CONCEPTUAL_PATTERNS = [
    re.compile(r"\bbecause\b|\btherefore\b|\bhowever\b", re.IGNORECASE),
    re.compile(r"\bwhy\b|\bhow\b(?!\s+many)", re.IGNORECASE),
    re.compile(r"\bcompare[sd]?\b|\bcontrast(s|ed)?\b", re.IGNORECASE),
    re.compile(r"\bimplies\b|\bsuggests\b|\bargu(e|es|ed|ment)\b", re.IGNORECASE),
    re.compile(r"\bfor example\b|\bfor instance\b", re.IGNORECASE),
    re.compile(r"\brelationship between\b|\btrade-?off\b", re.IGNORECASE),
]


def classify(text: str) -> tuple[str, float]:
    """Returns (content_type, memorization_score in [0, 1])."""
    mem_hits = sum(1 for p in _MEMORIZATION_PATTERNS if p.search(text))
    con_hits = sum(1 for p in _CONCEPTUAL_PATTERNS if p.search(text))
    total = mem_hits + con_hits
    if total == 0:
        return CONCEPTUAL, 0.5

    score = mem_hits / total
    if score - 0.5 >= CLASSIFY_MARGIN:
        return MEMORIZATION, score
    return CONCEPTUAL, score
