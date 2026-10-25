"""Verifier agent: fact-checks every narrated claim against the raw event data.

This is the 'explainable' guarantee: a sentence is only published if the events it
cites actually say what it says.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from ..models import Depth, Match, Narrative
from .analyst import insights_for, match_insights

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


# Wording that must accompany each score-state reason, so the prose cannot say "equaliser"
# about a goal that took the lead. Generous on purpose: it catches contradictions, not style.
_SCORE_WORDS: dict[str, tuple[str, ...]] = {
    "opens_scoring": ("open", "first", "deadlock", "lead", "ahead", "in front", "break"),
    "takes_lead": ("lead", "ahead", "in front", "deadlock", "advantage", "edge"),
    "equalises": ("level", "equal", "all square", "back on terms", "square", "draw"),
    "sent_off": ("sent off", "red card", "dismiss", "ten men", "down to", "send"),
    "cuts_deficit": ("back", "pull", "cut", "reduc", "deficit", "closer", "narrow", "consolation"),
    "extends_lead": ("extend", "doubl", "stretch", "wider", "increas", "further", "another",
                     "cushion", "ahead", "lead"),
}


def shows_figure(text: str, value: Any, key: str = "") -> bool:
    """True if the text states this evidence figure: a score like '1-0', or a number."""
    if isinstance(value, str):
        return mentions_score(text, value) if key.startswith("score") else value in text
    candidates = {f"{float(value):.2f}", f"{float(value):.1f}", f"{float(value):g}"}
    return any(re.search(rf"(?<![\d.]){re.escape(c)}(?!\d|\.\d)", text) for c in candidates)


def figures_match(expected: Any, found: Any) -> bool:
    if isinstance(expected, str) or isinstance(found, str):
        return expected == found
    try:
        return abs(float(expected) - float(found)) <= 0.051
    except (TypeError, ValueError):
        return False


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


def check_evidence(i: int, s: Any, known: dict, flag: Any) -> None:
    """Evidence figures a statement claims must equal the Analyst's, and the prose must state them."""
    evidence = s.claims.get("evidence", {})
    for code, figures in (evidence.items() if isinstance(evidence, dict) else []):
        if code not in known:
            flag(i, "evidence", sorted(known), code, f"evidence given for unsupported {code!r}")
            continue
        for key, value in (figures or {}).items():
            truth = known[code].evidence.get(key)
            if truth is None or not figures_match(truth, value):
                flag(i, "evidence", truth, value, f"{code}.{key} is {truth!r}, not {value!r}")
        for key, truth in known[code].evidence.items():
            if not shows_figure(s.text, truth, key):
                flag(i, "text", truth, s.text, f"text never states {key} = {truth!r} for {code!r}")


def check_why(i: int, s: Any, e: Any, match: Match, depth: Depth | None, flag: Any) -> None:
    """The reasons a statement gives for a moment must exist, say what they claim, and be right."""
    known = {ins.code: ins for ins in insights_for(match, e)}
    claimed = list(s.claims.get("why", []))
    text = s.text.lower()

    for code in claimed:
        if code not in known:
            flag(i, "why", sorted(known), code,
                 f"{code!r} is not supported by the events around event {e.id}")
            continue
        words = _SCORE_WORDS.get(code)
        if words and not any(w in text for w in words):
            flag(i, "text", code, s.text, f"text does not say what {code!r} means")

    check_evidence(i, s, known, flag)
    evidence = s.claims.get("evidence", {})

    if depth is not None and known:
        order = list(known)
        needed = order[:1] if Depth(depth) == Depth.CASUAL else order
        for code in needed:
            if code not in claimed:
                flag(i, "why", code, claimed, f"missing the reason {code!r} for event {e.id}")
            elif Depth(depth) == Depth.ANALYST and known[code].evidence and code not in evidence:
                flag(i, "evidence", code, None, f"analyst depth needs evidence for {code!r}")


def check_match_why(i: int, s: Any, match: Match, depth: Depth | None, flag: Any) -> None:
    """Reasons about the match as a whole (for example a dominant team that did not win)."""
    known = {ins.code: ins for ins in match_insights(match)}
    claimed = list(s.claims.get("match_why", []))
    for code in claimed:
        if code not in known:
            flag(i, "match_why", sorted(known), code,
                 f"{code!r} is not supported by the match as a whole")
    check_evidence(i, s, known, flag)
    evidence = s.claims.get("evidence", {})
    if depth is not None and Depth(depth) == Depth.ANALYST:
        for code in claimed:
            if code in known and known[code].evidence and code not in evidence:
                flag(i, "evidence", code, None, f"analyst depth needs evidence for {code!r}")


def verify(match: Match, narrative: Narrative, depth: Depth | None = None) -> Verification:
    """Fact-check a narrative. With `depth`, also require the explanation that depth promises:
    casual needs the first reason for each moment, analyst needs every reason plus its figures."""
    issues: list[Issue] = []
    checked = unverified = 0

    def flag(i: int, field: str, expected: Any, found: Any, msg: str) -> None:
        issues.append(Issue(statement_index=i, field=field, expected=expected, found=found,
                            message=f"Statement {i}: {msg}"))

    for i, s in enumerate(narrative.statements):
        has_final = "final_score" in s.claims or "score_so_far" in s.claims
        has_match_why = "match_why" in s.claims
        if not s.event_ids and not has_final and not has_match_why:
            if s.claims:
                flag(i, "event_ids", "at least one", [], "makes claims but cites no event")
            else:
                unverified += 1
            continue
        checked += 1

        if has_final:
            h, a = match.score_after()
            expected = f"{h}-{a}"
            label = "final_score" if "final_score" in s.claims else "score_so_far"
            what = "final score" if label == "final_score" else f"score after {match.clock} minutes"
            if label == "final_score" and not match.is_final:
                flag(i, label, "score_so_far", "final_score",
                     f"the match is not over (minute {match.clock}): use score_so_far")
            elif s.claims[label] != expected:
                flag(i, label, expected, s.claims[label],
                     f"{what} is {expected}, not {s.claims[label]}")
            if not states_final_score(s.text, match.home, match.away, h, a):
                flag(i, "text", expected, s.text, f"text does not state the {what}")

        if has_match_why:
            check_match_why(i, s, match, depth, flag)

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
            check_why(i, s, e, match, depth, flag)
            if e.player.split()[-1].lower() not in s.text.lower():
                flag(i, "text", e.player, s.text, f"text never mentions {e.player}")
            if not mentions_minute(s.text, e.minute):
                flag(i, "text", e.minute, s.text, f"text never mentions minute {e.minute}")

    if depth is not None:
        wanted = [ins.code for ins in match_insights(match)]
        needed = wanted[:1] if Depth(depth) == Depth.CASUAL else wanted
        claimed_codes = {c for s in narrative.statements for c in s.claims.get("match_why", [])}
        for code in needed:
            if code not in claimed_codes:
                issues.append(Issue(
                    statement_index=len(narrative.statements) - 1, field="match_why",
                    expected=code, found=sorted(claimed_codes),
                    message=f"Missing the match-level reason {code!r}: add a statement for it",
                ))

    return Verification(passed=not issues, checked=checked, unverified=unverified, issues=issues)
