"""Deterministic synthetic match generator.

All clubs and players are fictional. The same seed always produces the same match,
which keeps tests, demos and the Verifier reproducible.
"""

from __future__ import annotations

import math
import random

from ..models import Event, EventType, Match

HOME = "Northgate FC"
AWAY = "Harbour United"

SQUADS: dict[str, list[str]] = {
    HOME: [
        "Idris Calder", "Tomas Reyes", "Kofi Mensah", "Liam Hartley",
        "Ravi Anand", "Jonas Berg", "Eli Okafor", "Marco Silvestri",
    ],
    AWAY: [
        "Owen Pryce", "Samir Haddad", "Luca Moretti", "Declan Ward",
        "Arjun Menon", "Felix Brandt", "Yusuf Demir", "Callum Reid",
    ],
}

_TYPES = ["pass", "shot", "foul", "corner", "yellow_card"]
_WEIGHTS = [0.58, 0.18, 0.12, 0.08, 0.04]


def _other(team: str) -> str:
    return AWAY if team == HOME else HOME


def _xg(x: float, y: float) -> float:
    """Toy expected-goals model based on distance to goal (pitch 105m x 68m)."""
    dist = math.hypot((100 - x) * 1.05, (y - 50) * 0.68)
    return round(max(0.02, min(0.6, 0.35 - 0.012 * dist)), 2)


def _make_event(rng: random.Random, event_id: int, minute: int, kind: str, team: str) -> Event:
    player = rng.choice(SQUADS[team])
    if kind == "pass":
        return Event(
            id=event_id, minute=minute, type=EventType.PASS, team=team, player=player,
            x=round(rng.uniform(10, 95), 1), y=round(rng.uniform(5, 95), 1),
            detail=rng.choice(["short pass", "through ball", "long ball", "cross"]),
        )
    if kind == "shot":
        x, y = round(rng.uniform(72, 96), 1), round(rng.uniform(15, 85), 1)
        xg = _xg(x, y)
        roll = rng.random()
        if roll < xg * 1.4:
            etype, detail = EventType.GOAL, rng.choice(["right foot", "left foot", "header"])
        elif roll < 0.5:
            etype, detail = EventType.SAVE, "saved by the goalkeeper"
        else:
            etype, detail = EventType.SHOT, "off target"
        return Event(id=event_id, minute=minute, type=etype, team=team, player=player,
                     x=x, y=y, xg=xg, detail=detail)
    if kind == "corner":
        return Event(id=event_id, minute=minute, type=EventType.CORNER, team=team, player=player,
                     x=100.0, y=rng.choice([0.0, 100.0]), detail="corner kick")
    if kind == "foul":
        return Event(id=event_id, minute=minute, type=EventType.FOUL, team=team, player=player,
                     x=round(rng.uniform(20, 80), 1), y=round(rng.uniform(5, 95), 1),
                     detail="foul committed")
    return Event(id=event_id, minute=minute, type=EventType.YELLOW_CARD, team=team, player=player,
                 x=round(rng.uniform(20, 80), 1), y=round(rng.uniform(5, 95), 1),
                 detail="late challenge")


def _ensure_goals(events: list[Event], minimum: int) -> None:
    goals = sum(e.type == EventType.GOAL for e in events)
    candidates = sorted(
        (e for e in events if e.type in (EventType.SHOT, EventType.SAVE)), key=lambda e: -e.xg
    )
    for e in candidates[: max(0, minimum - goals)]:
        e.type, e.detail = EventType.GOAL, "right foot"


def generate_match(seed: int = 7, n_events: int = 70) -> Match:
    rng = random.Random(seed)
    minutes = sorted(rng.randint(1, 90) for _ in range(n_events))
    events = [
        Event(id=0, minute=0, type=EventType.KICKOFF, team=HOME,
              player=rng.choice(SQUADS[HOME]), x=50, y=50, detail="kick-off")
    ]
    possession = HOME
    for minute in minutes:
        if rng.random() < 0.35:
            possession = _other(possession)
        kind = rng.choices(_TYPES, weights=_WEIGHTS)[0]
        events.append(_make_event(rng, len(events), minute, kind, possession))
    events.append(
        Event(id=len(events), minute=90, type=EventType.FULL_TIME, team=HOME,
              player=rng.choice(SQUADS[HOME]), x=50, y=50, detail="full time")
    )
    _ensure_goals(events, minimum=2)
    return Match(home=HOME, away=AWAY, seed=seed, events=events)
