"""Analyst agent: turns raw events into structured match intelligence.

Deliberately deterministic: the numbers an LLM later narrates come from here, not from
the model, which is what makes the final output explainable.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ..models import Event, EventType, Match

WINDOW = 15
MAX_MOMENTS = 8


class Moment(BaseModel):
    event_id: int
    minute: int
    kind: str  # goal | big_chance | card
    headline: str
    facts: dict[str, Any]


class Analysis(BaseModel):
    final_score: str
    xg: dict[str, float]
    momentum: list[dict[str, Any]]
    key_moments: list[Moment]


def _threat(e: Event) -> float:
    if e.type in (EventType.SHOT, EventType.SAVE, EventType.GOAL):
        return 3.0
    if e.type == EventType.CORNER:
        return 1.0
    if e.type == EventType.PASS and e.x > 66:
        return 0.5
    return 0.0


def _facts(match: Match, e: Event) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "minute": e.minute, "player": e.player, "team": e.team,
        "type": e.type.value, "xg": e.xg, "detail": e.detail,
    }
    if e.type == EventType.GOAL:
        h, a = match.score_after(e.id)
        facts["score"] = f"{h}-{a}"
    return facts


def analyse(match: Match) -> Analysis:
    h, a = match.score_after()
    xg = {match.home: 0.0, match.away: 0.0}
    for e in match.events:
        xg[e.team] = round(xg[e.team] + e.xg, 2)

    n_windows = 90 // WINDOW
    threat = [{match.home: 0.0, match.away: 0.0} for _ in range(n_windows)]
    for e in match.events:
        if 1 <= e.minute <= 90:
            threat[min((e.minute - 1) // WINDOW, n_windows - 1)][e.team] += _threat(e)
    momentum = []
    for i, w in enumerate(threat):
        diff = w[match.home] - w[match.away]
        leader = "even" if abs(diff) < 1 else (match.home if diff > 0 else match.away)
        momentum.append({
            "window": f"{i * WINDOW + 1}-{(i + 1) * WINDOW}",
            "home": round(w[match.home], 1), "away": round(w[match.away], 1), "leader": leader,
        })

    goals = [e for e in match.events if e.type == EventType.GOAL]
    chances = sorted(
        (e for e in match.events if e.type in (EventType.SHOT, EventType.SAVE) and e.xg >= 0.25),
        key=lambda e: -e.xg,
    )
    cards = [e for e in match.events if e.type == EventType.YELLOW_CARD]
    chosen = (goals + chances + cards)[:MAX_MOMENTS]

    moments = []
    for e in sorted(chosen, key=lambda e: (e.minute, e.id)):
        if e.type == EventType.GOAL:
            kind, headline = "goal", f"{e.player} scores for {e.team} ({_facts(match, e)['score']})"
        elif e.type == EventType.YELLOW_CARD:
            kind, headline = "card", f"{e.player} ({e.team}) is booked"
        else:
            kind, headline = "big_chance", f"Big chance for {e.team}: {e.player} ({e.xg:.2f} xG)"
        moments.append(Moment(event_id=e.id, minute=e.minute, kind=kind,
                              headline=headline, facts=_facts(match, e)))

    return Analysis(final_score=f"{h}-{a}", xg=xg, momentum=momentum, key_moments=moments)
