"""Narrator agent: writes the match story.

Uses an LLM (Microsoft Foundry deployment) when configured, otherwise a deterministic
template. Every sentence carries structured `claims` that the Verifier checks.
"""

from __future__ import annotations

import json
from typing import Protocol

from pydantic import ValidationError

from ..models import Depth, Match, Narrative, Statement
from .analyst import Analysis, Moment


class NarrationError(RuntimeError):
    """Raised when the LLM output cannot be parsed into a Narrative."""


class JSONLLM(Protocol):
    available: bool

    def complete_json(self, system: str, user: str) -> dict: ...


SYSTEM_PROMPT = """You are a football match commentator. Write a short recap as JSON:
{"statements": [{"text": str, "event_ids": [int], "claims": {...}}]}
Rules:
- Use ONLY the facts provided. Never invent players, minutes, scores or events.
- Each statement about a moment must list that moment's event_id in event_ids and set
  claims with keys: minute (int), player (str), team (str), type (str) and, for goals,
  score (str like "1-0"). The text must mention the player and the minute.
- Write every minute as digits, like "minute 31" or "31st minute". Never spell numbers out.
- Write every score as digits with a plain hyphen, home team first, exactly like "0-1".
  Every goal statement must state the running score in that form.
- Finish with one statement whose claims are {"final_score": "<home>-<away>"}. Its text must
  name both teams and give the score home-first, like "Northgate FC 0-2 Harbour United".
- If the user message has "score_so_far" instead of "final_score", the match is still being
  played (see "minutes_played"). Finish with claims {"score_so_far": "<home>-<away>"} and text
  like "After 35 minutes: Northgate FC 1, Harbour United 0". Never call it final or full time,
  and never mention anything after minutes_played.
- Each moment lists `insights`: verified reasons the moment matters (code, text, evidence).
  Explain why the moment matters using ONLY those insights. Never add reasons of your own.
- The user message has a "depth". For "casual": use only the FIRST insight of each moment, in one
  short plain sentence; set claims.why to [that insight's code]. For "analyst": use EVERY insight,
  state each insight's evidence figures exactly as given, set claims.why to all their codes and
  claims.evidence to {code: the insight's evidence object}.
- For the score-state insights (opens_scoring, takes_lead, equalises, cuts_deficit, extends_lead)
  the wording must say the same thing: open the scoring, take the lead, level the score, pull a
  goal back, extend the lead.
- A moment of type "red_card" is a sending off: say the player is sent off.
- The user message may list `match_insights`: reasons about the match as a whole. Add one
  statement for each, just before the final statement, with claims {"match_why": [code]}
  (casual: the first only; analyst: all, with claims.evidence {code: evidence object}), and
  cite no event_ids. Use the insight's text closely.
- If the user message lists verifier issues from a previous draft, fix every one."""


def build_user_prompt(
    match: Match,
    analysis: Analysis,
    feedback: list[str] | None = None,
    depth: Depth = Depth.CASUAL,
) -> str:
    """The facts the model may use, plus any Verifier issues from the previous draft."""
    payload = {
        "home": match.home,
        "away": match.away,
        **(
            {"final_score": analysis.final_score}
            if match.is_final
            else {"score_so_far": analysis.final_score, "minutes_played": match.clock}
        ),
        "depth": Depth(depth).value,
        "match_insights": [i.model_dump() for i in analysis.match_insights],
        "moments": [
            {
                "event_id": m.event_id,
                **m.facts,
                "insights": [i.model_dump() for i in m.insights],
            }
            for m in analysis.key_moments
        ],
    }
    user = json.dumps(payload)
    if feedback:
        user += "\nVerifier issues from your previous draft:\n- " + "\n- ".join(feedback)
    return user


def extract_json(text: str) -> dict:
    """Pull the JSON object out of model text, tolerating ```json fences and chatter."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise NarrationError("no JSON object in model output")
    try:
        return json.loads(text[start : end + 1])
    except ValueError as exc:
        raise NarrationError(f"invalid JSON in model output: {exc}") from exc


def parse_narrative(data: dict, source: str = "llm") -> Narrative:
    try:
        statements = [Statement(**s) for s in data["statements"]]
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise NarrationError(f"unparseable LLM output: {exc}") from exc
    return Narrative(statements=statements, source=source)


def chosen_insights(moment: Moment, depth: Depth) -> list:
    """Casual fans get the single most important reason; analysts get every one."""
    return moment.insights[:1] if Depth(depth) == Depth.CASUAL else list(moment.insights)


def chosen_match_insights(found: list, depth: Depth) -> list:
    return found[:1] if Depth(depth) == Depth.CASUAL else list(found)


def template_narrative(
    match: Match, analysis: Analysis, depth: Depth = Depth.CASUAL
) -> Narrative:
    """Deterministic narration, correct by construction. Also the safety net."""
    statements = [Statement(text=f"Welcome to {match.home} against {match.away}.")]
    for m in analysis.key_moments:
        f = m.facts
        claims: dict = {k: f[k] for k in ("minute", "player", "team", "type")}
        if m.kind == "goal":
            claims["score"] = f["score"]
            text = (f"Goal! In minute {f['minute']}, {f['player']} scores for {f['team']}. "
                    f"It's {f['score']}.")
        elif m.kind == "red_card":
            text = f"Minute {f['minute']}: {f['player']} of {f['team']} is sent off."
        elif m.kind == "card":
            text = f"Minute {f['minute']}: {f['player']} of {f['team']} is booked for a late challenge."
        else:
            text = (f"Minute {f['minute']}: a big chance for {f['team']}. {f['player']}'s effort is "
                    f"worth {f['xg']:.2f} expected goals.")
        why = chosen_insights(m, depth)
        if why:
            text += " " + " ".join(i.text for i in why)
            claims["why"] = [i.code for i in why]
            if Depth(depth) == Depth.ANALYST:
                claims["evidence"] = {i.code: i.evidence for i in why if i.evidence}
        statements.append(Statement(text=text, event_ids=[m.event_id], claims=claims))
    for insight in chosen_match_insights(analysis.match_insights, depth):
        claims = {"match_why": [insight.code]}
        if Depth(depth) == Depth.ANALYST:
            claims["evidence"] = {insight.code: insight.evidence}
        statements.append(Statement(text=insight.text, claims=claims))
    h, a = analysis.final_score.split("-")
    if match.is_final:
        closing = f"Full time: {match.home} {h}, {match.away} {a}."
        statements.append(Statement(text=closing, claims={"final_score": analysis.final_score}))
    else:
        closing = f"After {match.clock} minutes: {match.home} {h}, {match.away} {a}."
        statements.append(Statement(text=closing, claims={"score_so_far": analysis.final_score}))
    return Narrative(statements=statements, source="template")


class Narrator:
    def __init__(self, llm: JSONLLM | None = None) -> None:
        self.llm = llm

    def narrate(
        self,
        match: Match,
        analysis: Analysis,
        feedback: list[str] | None = None,
        depth: Depth = Depth.CASUAL,
    ) -> Narrative:
        if self.llm is None or not self.llm.available:
            return template_narrative(match, analysis, depth)
        user = build_user_prompt(match, analysis, feedback, depth)
        try:
            data = self.llm.complete_json(SYSTEM_PROMPT, user)
        except ValueError as exc:
            raise NarrationError(f"unparseable LLM output: {exc}") from exc
        return parse_narrative(data)
