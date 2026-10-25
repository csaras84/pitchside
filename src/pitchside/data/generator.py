"""Deterministic synthetic match generator.

All clubs and players are fictional. The same seed always produces the same match,
which keeps tests, demos and the Verifier reproducible.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable

from ..models import Event, EventType, Match, Plant

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


def _make_event(
    rng: random.Random, event_id: int, minute: int, kind: str, team: str, allow_goals: bool = True
) -> Event:
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
        if allow_goals and roll < xg * 1.4:
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


ARCHETYPES = ("red_card_swing", "late_comeback", "dominant_wasteful")
_BASE = [0.58, 0.18, 0.12, 0.08, 0.04]  # same order as _TYPES

Weights = Callable[[int, str], list[float]]


def _scripted_goal(rng: random.Random, team: str, minute: int) -> Event:
    x, y = round(rng.uniform(82, 95), 1), round(rng.uniform(30, 70), 1)
    return Event(
        id=0, minute=minute, type=EventType.GOAL, team=team, player=rng.choice(SQUADS[team]),
        x=x, y=y, xg=_xg(x, y), detail=rng.choice(["right foot", "left foot", "header"]),
    )


def _plan(
    rng: random.Random, archetype: str
) -> tuple[str, Callable[[int], float], Weights, list[Event], list[Plant]]:
    """The script for a story: who it is about, how possession and shot choice drift over the
    match, the goals and cards that are written in, and the storylines being planted.

    Random goals are switched off in story matches, so the scripted ones are the only goals.
    """
    a, b = (HOME, AWAY) if rng.random() < 0.5 else (AWAY, HOME)

    if archetype == "red_card_swing":
        r = rng.randint(50, 62)
        x, y = round(rng.uniform(25, 70), 1), round(rng.uniform(10, 90), 1)
        red = Event(id=0, minute=r, type=EventType.RED_CARD, team=a, player=rng.choice(SQUADS[a]),
                    x=x, y=y, detail="serious foul play")
        goals = [_scripted_goal(rng, b, r + rng.randint(5, 12)),
                 _scripted_goal(rng, b, r + rng.randint(16, 26))]

        def share(m: int) -> float:
            return 0.5 if m < r else 0.3

        def weights(m: int, team: str) -> list[float]:
            if m < r:
                return _BASE
            return [0.50, 0.30, 0.08, 0.10, 0.02] if team == b else [0.64, 0.10, 0.14, 0.06, 0.06]

        plant = Plant(code="red_card_swing", team=a, minute=r,
                      note=f"{a} play the rest of the match with ten men and {b} take control.")
        return a, share, weights, [red, *goals], [plant]

    if archetype == "late_comeback":
        goals = [_scripted_goal(rng, b, rng.randint(12, 24)), _scripted_goal(rng, b, rng.randint(30, 42)),
                 _scripted_goal(rng, a, rng.randint(66, 74)), _scripted_goal(rng, a, rng.randint(80, 84)),
                 _scripted_goal(rng, a, rng.randint(86, 89))]

        def share(m: int) -> float:
            return 0.38 if m < 55 else (0.55 if m < 65 else 0.72)

        def weights(m: int, team: str) -> list[float]:
            if m >= 65 and team == a:
                return [0.46, 0.30, 0.10, 0.12, 0.02]
            return _BASE

        plant = Plant(code="late_comeback", team=a, minute=goals[3].minute,
                      note=f"{a} come back from 0-2 down with late goals and win.")
        return a, share, weights, goals, [plant]

    if archetype == "dominant_wasteful":
        goals = [_scripted_goal(rng, b, rng.randint(68, 84))]

        def share(m: int) -> float:
            return 0.68

        def weights(m: int, team: str) -> list[float]:
            return [0.45, 0.30, 0.10, 0.13, 0.02] if team == a else [0.65, 0.08, 0.15, 0.06, 0.06]

        plant = Plant(code="dominant_wasteful", team=a, minute=90,
                      note=f"{a} dominate the chances but {b} win with one counter-attack goal.")
        return a, share, weights, goals, [plant]

    raise ValueError(f"unknown archetype {archetype!r}; choose one of {list(ARCHETYPES)}")


_SHOT_LIKE = (EventType.SHOT, EventType.SAVE, EventType.GOAL)


def _shots(body: list[Event], team: str, lo: int, hi: int) -> int:
    """Shots by `team` in minutes lo < minute <= hi: a plain count, not the Analyst's threat score."""
    return sum(1 for e in body if e.team == team and e.type in _SHOT_LIKE and lo < e.minute <= hi)


def _add_shot(rng: random.Random, body: list[Event], team: str, lo: int, hi: int,
              close: bool = False) -> None:
    shot = _make_event(rng, 0, rng.randint(lo + 1, hi), "shot", team, allow_goals=False)
    if close:  # a clear chance from inside the box
        x, y = round(rng.uniform(86, 94), 1), round(rng.uniform(30, 70), 1)
        shot = shot.model_copy(update={"x": x, "y": y, "xg": _xg(x, y)})
    body.append(shot)


def _make_premise_true(rng: random.Random, body: list[Event], plant: Plant, other: str) -> None:
    """A planted storyline is ground truth, so it has to hold in the data. Random events do not
    always deliver it, so add shots until it does. Counts and the xG field are used here, never
    the Analyst's own measures, so finding the story is still a real test of the Analyst."""
    team, minute = plant.team, plant.minute
    if plant.code == "red_card_swing":
        for _ in range(30):
            before = _shots(body, other, minute - 16, minute - 1) - _shots(body, team, minute - 16, minute - 1)
            after = _shots(body, other, minute, minute + 15) - _shots(body, team, minute, minute + 15)
            if after >= 4 and after - before >= 4:
                return
            if after < 4:
                _add_shot(rng, body, other, minute, min(minute + 14, 89))
            else:
                _add_shot(rng, body, team, minute - 16, minute - 1)
    elif plant.code == "dominant_wasteful":
        for _ in range(30):
            if sum(e.xg for e in body if e.team == team) - sum(e.xg for e in body if e.team == other) >= 1.4:
                return
            _add_shot(rng, body, team, 0, 89, close=True)


def _generate_story(seed: int, n_events: int, archetype: str) -> Match:
    rng = random.Random(f"{archetype}:{seed}")
    a, share, weights, scripted, plants = _plan(rng, archetype)
    b = AWAY if a == HOME else HOME
    minutes = sorted(rng.randint(1, 90) for _ in range(n_events))
    body: list[Event] = []
    for minute in minutes:
        team = a if rng.random() < share(minute) else b
        kind = rng.choices(_TYPES, weights=weights(minute, team))[0]
        body.append(_make_event(rng, 0, minute, kind, team, allow_goals=False))
    body += scripted
    for plant in plants:
        _make_premise_true(rng, body, plant, b)
    body.sort(key=lambda e: e.minute)  # stable: written-in events follow the random ones
    events = [Event(id=0, minute=0, type=EventType.KICKOFF, team=HOME,
                    player=rng.choice(SQUADS[HOME]), x=50, y=50, detail="kick-off")]
    events += [e.model_copy(update={"id": i}) for i, e in enumerate(body, start=1)]
    events.append(Event(id=len(events), minute=90, type=EventType.FULL_TIME, team=HOME,
                        player=rng.choice(SQUADS[HOME]), x=50, y=50, detail="full time"))
    return Match(home=HOME, away=AWAY, seed=seed, events=events, planted=plants)


def generate_match(seed: int = 7, n_events: int = 70, archetype: str | None = None) -> Match:
    """A synthetic match. With an archetype, a scripted story is written into it."""
    if archetype:
        return _generate_story(seed, n_events, archetype)
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
