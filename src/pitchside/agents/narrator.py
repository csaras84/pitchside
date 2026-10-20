"""Narrator agent: writes the match story.

Uses an LLM (Microsoft Foundry deployment) when configured, otherwise a deterministic
template. Every sentence carries structured `claims` that the Verifier checks.
"""

from __future__ import annotations

import json
from typing import Protocol

from pydantic import ValidationError

from ..models import Match, Narrative, Statement
from .analyst import Analysis


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
- Finish with one statement whose claims are {"final_score": "<home>-<away>"} and whose
  text states the final score.
- If the user message lists verifier issues from a previous draft, fix every one."""


def template_narrative(match: Match, analysis: Analysis) -> Narrative:
    """Deterministic narration, correct by construction. Also the safety net."""
    statements = [Statement(text=f"Welcome to {match.home} against {match.away}.")]
    for m in analysis.key_moments:
        f = m.facts
        claims = {k: f[k] for k in ("minute", "player", "team", "type")}
        if m.kind == "goal":
            claims["score"] = f["score"]
            text = (f"Goal! In minute {f['minute']}, {f['player']} scores for {f['team']}. "
                    f"It's {f['score']}.")
        elif m.kind == "card":
            text = f"Minute {f['minute']}: {f['player']} of {f['team']} is booked for a late challenge."
        else:
            text = (f"Minute {f['minute']}: a big chance for {f['team']}. {f['player']}'s effort is "
                    f"worth {f['xg']:.2f} expected goals.")
        statements.append(Statement(text=text, event_ids=[m.event_id], claims=claims))
    h, a = analysis.final_score.split("-")
    statements.append(Statement(
        text=f"Full time: {match.home} {h}, {match.away} {a}.",
        claims={"final_score": analysis.final_score},
    ))
    return Narrative(statements=statements, source="template")


class Narrator:
    def __init__(self, llm: JSONLLM | None = None) -> None:
        self.llm = llm

    def narrate(
        self, match: Match, analysis: Analysis, feedback: list[str] | None = None
    ) -> Narrative:
        if self.llm is None or not self.llm.available:
            return template_narrative(match, analysis)
        payload = {
            "home": match.home,
            "away": match.away,
            "final_score": analysis.final_score,
            "moments": [{"event_id": m.event_id, **m.facts} for m in analysis.key_moments],
        }
        user = json.dumps(payload)
        if feedback:
            user += "\nVerifier issues from your previous draft:\n- " + "\n- ".join(feedback)
        try:
            data = self.llm.complete_json(SYSTEM_PROMPT, user)
            statements = [Statement(**s) for s in data["statements"]]
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise NarrationError(f"unparseable LLM output: {exc}") from exc
        return Narrative(statements=statements, source="llm")
