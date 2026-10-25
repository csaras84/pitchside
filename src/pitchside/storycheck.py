"""Evaluation: did the Analyst find the storylines the generator planted?

The generator writes a storyline into a synthetic match (a red-card swing, a late comeback,
a dominant team that failed to win) and records it as ground truth. The agents never see that
record. This module compares it with what the Analyst worked out from the raw events alone,
so "the system understands the match" becomes a measurement, not a claim.
"""

from __future__ import annotations

from pydantic import BaseModel

from .agents.analyst import Analysis
from .models import Match, Plant


class StoryCheck(BaseModel):
    code: str
    team: str
    minute: int
    note: str  # what the generator planted
    recovered: bool  # did the Analyst find it?
    found: str  # what the Analyst found, in words


def _recover(plant: Plant, analysis: Analysis) -> tuple[bool, str]:
    if plant.code == "red_card_swing":
        moment = next(
            (m for m in analysis.key_moments
             if m.kind == "red_card" and m.minute == plant.minute
             and m.facts["team"] == plant.team),
            None,
        )
        if moment is None:
            return False, "did not pick out the sending off"
        codes = {i.code for i in moment.insights}
        if {"sent_off", "momentum_shift"} <= codes:
            return True, "the sending off and the swing in control that followed"
        return False, "found the sending off but not the swing that followed"

    if plant.code == "late_comeback":
        for m in analysis.key_moments:
            codes = {i.code for i in m.insights}
            if (m.kind == "goal" and m.facts["team"] == plant.team and "late_goal" in codes
                    and codes & {"equalises", "takes_lead"}):
                return True, f"a late goal that changed the scoreline, in minute {m.minute}"
        return False, "found no late goal that levelled or won the match"

    if plant.code == "dominant_wasteful":
        for ins in analysis.match_insights:
            if ins.code == "wasted_dominance" and plant.team in ins.text:
                return True, "better chances, but the result did not follow"
        return False, "did not flag the gap between chances and result"

    return False, "unknown storyline"


def check_planted(match: Match, analysis: Analysis) -> list[StoryCheck]:
    if not match.is_final:
        return []
    out = []
    for plant in match.planted:
        recovered, found = _recover(plant, analysis)
        out.append(StoryCheck(**plant.model_dump(), recovered=recovered, found=found))
    return out
