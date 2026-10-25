"""Deliberate faults for the Verifier demo.

The model is non-deterministic, so a real rejection cannot be summoned on demand. For a
reproducible demonstration this module corrupts the first draft in the way a careless writer
might (a wrong minute, a wrong score) and the pipeline's trace labels it as INJECTED. The
Verifier is not told: it has to find the fault by checking the draft against the raw events.
"""

from __future__ import annotations

import re

from .models import Narrative

FAULTS = ("wrong_minute", "wrong_score")


def _first(narrative: Narrative, key: str) -> int:
    for i, s in enumerate(narrative.statements):
        if key in s.claims and s.event_ids:
            return i
    raise ValueError(f"no statement with a {key!r} claim to corrupt")


def inject(narrative: Narrative, fault: str) -> tuple[Narrative, str]:
    """A corrupted copy of the draft, and a one-line description of what was changed."""
    if fault not in FAULTS:
        raise ValueError(f"unknown fault {fault!r}; expected one of {list(FAULTS)}")
    draft = narrative.model_copy(deep=True)
    if fault == "wrong_minute":
        i = _first(draft, "minute")
        s = draft.statements[i]
        old = int(s.claims["minute"])
        new = old + 7 if old + 7 <= 89 else old - 7
        s.claims["minute"] = new
        s.text = re.sub(rf"(?<!\d){old}(?!\d)", str(new), s.text, count=1)
        return draft, f"changed the minute of one event from {old} to {new}"
    i = _first(draft, "score")
    s = draft.statements[i]
    old = str(s.claims["score"])
    home, away = (int(x) for x in old.split("-"))
    new = f"{home + 1}-{away}"
    s.claims["score"] = new
    s.text = re.sub(rf"(?<!\d){home}\s*[-–]\s*{away}(?!\d)", new, s.text, count=1)
    return draft, f"changed the score after one goal from {old} to {new}"
