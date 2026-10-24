"""Verifier agent: fact-checks every narrated claim against the raw event data.

This is the 'explainable' guarantee: a sentence is only published if the events it
cites actually say what it says.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from ..models import Match, Narrative

_DASHES = str.maketrans({"\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2010": "-", "\u2011": "-"})


def mentions_minute(text: str, minute: int) -> bool:
    """True if the text names the minute as a number: 'minute 9', '9th minute', "9'", '45+2'.

    Digits must stand alone, so 'minute 19' or 'minute 90' never satisfy a claim about 9.
    """
    return re.search(rf"(?<!\d){minute}(?:st|nd|rd|th)?(?!\d)", text) is not None


def mentions_score(text: str, score: str) -> bool:
    """True if the text states the score 'H-A' with any dash style or spacing: '0-1', '0 – 1'."""
    home, away = score.split("-")
    cleaned = text.translate(_DASHES)
    return re.search(rf"(?<!\d){home}\s*-\s*{away}(?!\d)", cleaned) is not None


def states_final_score(text: str, home: str, away: str, home_goals: int, away_goals: int) -> bool:
    """True only if the text gives the final score with the goals attached to the right teams.

    Accepts '0-2' (home first, any dash style) or 'Home 0, Away 2' naming both teams.
    Digits merely appearing somewhere ('Northgate won 2-0') do not count.
    """
    if mentions_score(text, f"{home_goals}-{away_goals}"):
        return True
    pattern = (
        rf"{re.escape(home)}\W+{home_goals}(?!\d).*{re.escape(away)}\W+{away_goals}(?!\d)"
    )
    return re.search(pattern, text, re.DOTALL) is not None


class Issue(BaseModel):
    statement_index: int
    field: str
    expected: Any
    found: Any
    message: str


class Verification(BaseModel):
    passed: bool
    checked: int
    unverified: int
    issues: list[Issue]


def verify(match: Match, narrative: Narrative) -> Verification:
    issues: list[Issue] = []
    checked = unverified = 0

    def flag(i: int, field: str, expected: Any, found: Any, msg: str) -> None:
        issues.append(Issue(statement_index=i, field=field, expected=expected, found=found,
                            message=f"Statement {i}: {msg}"))

    for i, s in enumerate(narrative.statements):
        has_final = "final_score" in s.claims
        if not s.event_ids and not has_final:
            if s.claims:
                flag(i, "event_ids", "at least one", [], "makes claims but cites no event")
            else:
                unverified += 1
            continue
        checked += 1

        if has_final:
            h, a = match.score_after()
            expected = f"{h}-{a}"
            if s.claims["final_score"] != expected:
                flag(i, "final_score", expected, s.claims["final_score"],
                     f"final score is {expected}, not {s.claims['final_score']}")
            if not states_final_score(s.text, match.home, match.away, h, a):
                flag(i, "text", expected, s.text, "text does not state the final score")

        for event_id in s.event_ids:
            e = match.event_by_id(event_id)
            if e is None:
                flag(i, "event_ids", "existing event", event_id, f"event {event_id} does not exist")
                continue
            expected_fields = {
                "minute": e.minute, "team": e.team, "type": e.type.value,
            }
            for key, expected in expected_fields.items():
                if key in s.claims and s.claims[key] != expected:
                    flag(i, key, expected, s.claims[key],
                         f"{key} is {s.claims[key]!r} but event {event_id} says {expected!r}")
            if "player" in s.claims and s.claims["player"].lower() != e.player.lower():
                flag(i, "player", e.player, s.claims["player"],
                     f"player is {s.claims['player']!r} but event {event_id} says {e.player!r}")
            if "score" in s.claims:
                h, a = match.score_after(event_id)
                if s.claims["score"] != f"{h}-{a}":
                    flag(i, "score", f"{h}-{a}", s.claims["score"],
                         f"score after event {event_id} is {h}-{a}, not {s.claims['score']}")
                elif not mentions_score(s.text, s.claims["score"]):
                    flag(i, "text", s.claims["score"], s.text, "text does not state the score")
            # The prose must agree with the claims, not just the claims with the data.
            if e.player.split()[-1].lower() not in s.text.lower():
                flag(i, "text", e.player, s.text, f"text never mentions {e.player}")
            if not mentions_minute(s.text, e.minute):
                flag(i, "text", e.minute, s.text, f"text never mentions minute {e.minute}")

    return Verification(passed=not issues, checked=checked, unverified=unverified, issues=issues)
