"""Analyst agent: turns raw events into structured match intelligence.

Deliberately deterministic: the numbers an LLM later narrates come from here, not from
the model, which is what makes the final output explainable.

It also answers "why does this moment matter?". Each key moment carries `insights`:
short explanations such as "takes the lead" or "against the run of play", each with the
exact figures behind it. An insight exists only if the events support it, so there is
never a reason to invent one. The Verifier recomputes them from the raw events.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..models import Event, EventType, Match

WINDOW = 15
MAX_MOMENTS = 8
MAX_INSIGHTS = 3
PRESSURE_GAP = 3.0  # threat difference (about one shot) that counts as "on top"
SHIFT_GAP = 4.0  # change in that difference that counts as a swing in control
MIN_BEFORE = 5  # minutes of history needed before we talk about the run of play
MIN_AFTER = 8  # minutes of aftermath needed before we talk about a swing
BIG_CHANCE_XG = 0.25
LATE_MINUTE = 80
STAKES_MINUTE = 30  # before this a goal "levelling" the score is not yet a story
LEAD_MINUTE = 60  # before this, "a goal would give the lead" is true of every chance
SETTLED_MINUTE = 15  # before this, "best chance so far" is trivially true
WASTED_XG_GAP = 1.0  # expected-goals lead that makes "did not win" a story

SCORE_STATE_CODES = ("opens_scoring", "takes_lead", "equalises", "cuts_deficit", "extends_lead")


class Insight(BaseModel):
    code: str  # machine-readable reason; the Verifier checks claims against it
    text: str  # plain-English explanation
    evidence: dict[str, Any] = Field(default_factory=dict)  # the figures the text relies on


class Moment(BaseModel):
    event_id: int
    minute: int
    kind: str  # goal | big_chance | card | red_card
    headline: str
    facts: dict[str, Any]
    insights: list[Insight] = Field(default_factory=list)


class Analysis(BaseModel):
    final_score: str  # the score so far when the match is still being played
    clock: int = 90
    xg: dict[str, float]
    momentum: list[dict[str, Any]]
    key_moments: list[Moment]
    match_insights: list[Insight] = Field(default_factory=list)  # about the match as a whole


def _threat(e: Event) -> float:
    if e.type in (EventType.SHOT, EventType.SAVE, EventType.GOAL):
        return 3.0
    if e.type == EventType.CORNER:
        return 1.0
    if e.type == EventType.PASS and e.x > 66:
        return 0.5
    return 0.0


def threat_between(match: Match, lo: int, hi: int) -> dict[str, float]:
    """Attacking threat per team for events in minutes lo < minute <= hi."""
    out = {match.home: 0.0, match.away: 0.0}
    for e in match.events:
        if lo < e.minute <= hi:
            out[e.team] += _threat(e)
    return {team: round(v, 1) for team, v in out.items()}


def _facts(match: Match, e: Event) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "minute": e.minute, "player": e.player, "team": e.team,
        "type": e.type.value, "xg": e.xg, "detail": e.detail,
    }
    if e.type == EventType.GOAL:
        h, a = match.score_after(e.id)
        facts["score"] = f"{h}-{a}"
    return facts


def _score_before(match: Match, e: Event) -> tuple[int, int]:
    home = away = 0
    for other in match.events:
        if other.id == e.id:
            break
        if other.type == EventType.GOAL:
            if other.team == match.home:
                home += 1
            else:
                away += 1
    return home, away


def _before(match: Match, e: Event) -> tuple[dict[str, float], int] | None:
    """Threat in the minutes before the event, and how many minutes that covers."""
    lo, hi = max(0, e.minute - WINDOW - 1), e.minute - 1
    span = hi - lo
    if span < MIN_BEFORE:
        return None
    return threat_between(match, lo, hi), span


def _after(match: Match, e: Event) -> tuple[dict[str, float], int] | None:
    """Threat in the minutes after the event (up to the clock), and how many that covers."""
    hi = min(e.minute + WINDOW, match.clock)
    span = hi - e.minute
    if span < MIN_AFTER:
        return None
    return threat_between(match, e.minute, hi), span


def _shift_insight(match: Match, e: Event, team: str, other: str) -> Insight | None:
    """Did `team` take control after this event? Compares threat before and after."""
    before, after = _before(match, e), _after(match, e)
    if not (before and after):
        return None
    (b, _), (a, span) = before, after
    shift = (a[team] - a[other]) - (b[team] - b[other])
    if shift < SHIFT_GAP or a[team] <= a[other]:
        return None
    return Insight(
        code="momentum_shift",
        evidence={"threat_after_team": a[team], "threat_after_other": a[other],
                  "threat_before_team": b[team], "threat_before_other": b[other]},
        text=(f"{team} took control afterwards: attacking threat {a[team]} to {a[other]} over "
              f"the next {span} minutes, against {b[team]} to {b[other]} before."),
    )


def _goal_insights(match: Match, e: Event, other: str) -> list[Insight]:
    h0, a0 = _score_before(match, e)
    mine0, theirs0 = (h0, a0) if e.team == match.home else (a0, h0)
    mine1 = mine0 + 1
    h1, a1 = (mine1, theirs0) if e.team == match.home else (theirs0, mine1)
    score = f"{h1}-{a1}"
    state = {"score_after": score}
    out: list[Insight] = []

    if h0 + a0 == 0:
        out.append(Insight(code="opens_scoring", evidence=state,
                           text=f"Opens the scoring for {e.team}: it is {score}."))
    elif mine0 == theirs0:
        out.append(Insight(code="takes_lead", evidence=state,
                           text=f"Breaks the deadlock: {e.team} take the lead, {score}."))
    elif mine0 + 1 == theirs0:
        out.append(Insight(code="equalises", evidence=state,
                           text=f"Equaliser: {e.team} are level again at {score}."))
    elif mine1 < theirs0:
        out.append(Insight(code="cuts_deficit", evidence=state,
                           text=f"Pulls a goal back: {e.team} still trail, {score}."))
    else:
        out.append(Insight(code="extends_lead", evidence=state,
                           text=f"Extends the lead: {e.team} are {mine1 - theirs0} ahead, {score}."))

    if e.minute >= LATE_MINUTE and out[0].code in ("opens_scoring", "takes_lead", "equalises"):
        out.append(Insight(code="late_goal", evidence={"minute": e.minute},
                           text=f"It comes late, in minute {e.minute}."))

    before = _before(match, e)
    if before:
        threat, span = before
        mine, theirs = threat[e.team], threat[other]
        if theirs - mine >= PRESSURE_GAP:
            out.append(Insight(
                code="against_the_run",
                evidence={"threat_other": theirs, "threat_team": mine},
                text=(f"Against the run of play: {other} had the better of the previous {span} "
                      f"minutes, attacking threat {theirs} to {mine}."),
            ))
    shift = _shift_insight(match, e, e.team, other)
    if shift:
        out.append(shift)
    if e.xg < 0.10:
        out.append(Insight(code="long_shot", evidence={"xg": e.xg},
                           text=f"A difficult chance: only {e.xg:.2f} expected goals."))
    return out


def _chance_insights(match: Match, e: Event, other: str) -> list[Insight]:
    h0, a0 = _score_before(match, e)
    mine0, theirs0 = (h0, a0) if e.team == match.home else (a0, h0)
    score = f"{h0}-{a0}"
    out: list[Insight] = []
    if mine0 + 1 == theirs0 and e.minute >= STAKES_MINUTE:
        out.append(Insight(code="would_have_levelled", evidence={"score_before": score},
                           text=f"At {score}, a goal here would have levelled the match "
                                f"for {e.team}."))
    elif mine0 == theirs0 and e.minute >= LEAD_MINUTE:
        out.append(Insight(code="would_have_led", evidence={"score_before": score},
                           text=f"At {score}, a goal here would have put {e.team} ahead."))
    before = _before(match, e)
    if before:
        threat, span = before
        if threat[e.team] - threat[other] >= PRESSURE_GAP:
            out.append(Insight(
                code="sustained_pressure",
                evidence={"threat_team": threat[e.team], "threat_other": threat[other]},
                text=(f"{e.team} had been on top: attacking threat {threat[e.team]} to "
                      f"{threat[other]} over the previous {span} minutes."),
            ))
    better = sum(
        1 for x in match.events
        if x.id < e.id and x.type in (EventType.SHOT, EventType.SAVE, EventType.GOAL)
        and x.xg > e.xg
    )
    if better < 3 and e.minute >= SETTLED_MINUTE:
        out.append(Insight(
            code="chance_quality", evidence={"xg": e.xg},
            text=f"One of the three best chances so far: {e.xg:.2f} expected goals.",
        ))
    return out


def _card_insights(match: Match, e: Event, other: str) -> list[Insight]:
    out: list[Insight] = []
    before = _before(match, e)
    if before:
        threat, span = before
        if threat[other] - threat[e.team] >= PRESSURE_GAP:
            out.append(Insight(
                code="defending_under_pressure",
                evidence={"threat_other": threat[other], "threat_team": threat[e.team]},
                text=(f"{e.team} had been under pressure: {other} led on attacking threat "
                      f"{threat[other]} to {threat[e.team]} over the previous {span} minutes."),
            ))
    earlier = any(
        x.type == EventType.YELLOW_CARD for x in match.events if x.id < e.id
    )
    if not earlier:
        out.append(Insight(code="first_booking", text="The first booking of the match."))
    return out


def _red_insights(match: Match, e: Event, other: str) -> list[Insight]:
    reds = sum(1 for x in match.events
               if x.type == EventType.RED_CARD and x.team == e.team and x.id <= e.id)
    left = 11 - reds
    out = [Insight(code="sent_off", evidence={"players_left": left},
                   text=f"Sent off: {e.team} are down to {left} players.")]
    shift = _shift_insight(match, e, other, e.team)
    if shift:
        out.append(shift)
    return out


def insights_for(match: Match, e: Event) -> list[Insight]:
    """Why this event matters, most important first. Empty when nothing is supported."""
    other = match.away if e.team == match.home else match.home
    if e.type == EventType.GOAL:
        found = _goal_insights(match, e, other)
    elif e.type in (EventType.SHOT, EventType.SAVE) and e.xg >= BIG_CHANCE_XG:
        found = _chance_insights(match, e, other)
    elif e.type == EventType.YELLOW_CARD:
        found = _card_insights(match, e, other)
    elif e.type == EventType.RED_CARD:
        found = _red_insights(match, e, other)
    else:
        found = []
    return found[:MAX_INSIGHTS]


def match_insights(match: Match) -> list[Insight]:
    """Reasons about the match as a whole. Only meaningful once the match is over."""
    if not match.is_final:
        return []
    xg = {match.home: 0.0, match.away: 0.0}
    for e in match.events:
        xg[e.team] = round(xg[e.team] + e.xg, 2)
    h, a = match.score_after()
    out: list[Insight] = []
    for team, other, mine, theirs in ((match.home, match.away, h, a), (match.away, match.home, a, h)):
        if xg[team] - xg[other] >= WASTED_XG_GAP and mine <= theirs:
            out.append(Insight(
                code="wasted_dominance",
                evidence={"xg_team": xg[team], "xg_other": xg[other], "score": f"{h}-{a}"},
                text=(f"{team} had the better chances, expected goals {xg[team]:.2f} to "
                      f"{xg[other]:.2f}, yet did not win: the match finished {h}-{a}."),
            ))
    return out


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
        (e for e in match.events
         if e.type in (EventType.SHOT, EventType.SAVE) and e.xg >= BIG_CHANCE_XG),
        key=lambda e: -e.xg,
    )
    reds = [e for e in match.events if e.type == EventType.RED_CARD]
    cards = [e for e in match.events if e.type == EventType.YELLOW_CARD]
    chosen = (reds + goals + chances + cards)[:MAX_MOMENTS]

    moments = []
    for e in sorted(chosen, key=lambda e: (e.minute, e.id)):
        if e.type == EventType.GOAL:
            kind, headline = "goal", f"{e.player} scores for {e.team} ({_facts(match, e)['score']})"
        elif e.type == EventType.RED_CARD:
            kind, headline = "red_card", f"{e.player} ({e.team}) is sent off"
        elif e.type == EventType.YELLOW_CARD:
            kind, headline = "card", f"{e.player} ({e.team}) is booked"
        else:
            kind, headline = "big_chance", f"Big chance for {e.team}: {e.player} ({e.xg:.2f} xG)"
        moments.append(Moment(event_id=e.id, minute=e.minute, kind=kind, headline=headline,
                              facts=_facts(match, e), insights=insights_for(match, e)))

    return Analysis(final_score=f"{h}-{a}", clock=match.clock, xg=xg, momentum=momentum,
                    key_moments=moments, match_insights=match_insights(match))
