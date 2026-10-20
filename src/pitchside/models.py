"""Shared data models.

Pitch coordinates: x and y are both 0-100.
  x = progress up the pitch from the *acting team's own goal* (0) towards the goal
      they attack (100).
  y = position across the pitch from the acting team's perspective while facing the
      goal they attack: 0 is their left touchline, 100 is their right touchline.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    KICKOFF = "kickoff"
    PASS = "pass"
    SHOT = "shot"
    SAVE = "save"
    GOAL = "goal"
    FOUL = "foul"
    YELLOW_CARD = "yellow_card"
    CORNER = "corner"
    FULL_TIME = "full_time"


class Event(BaseModel):
    id: int
    minute: int = Field(ge=0, le=120)
    type: EventType
    team: str
    player: str
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    xg: float = Field(default=0.0, ge=0, le=1)
    detail: str = ""


class Match(BaseModel):
    home: str
    away: str
    seed: int
    events: list[Event]

    def event_by_id(self, event_id: int) -> Event | None:
        return next((e for e in self.events if e.id == event_id), None)

    def score_after(self, event_id: int | None = None) -> tuple[int, int]:
        """Score (home, away) after the given event id, or at full time if None."""
        home = away = 0
        for e in self.events:
            if e.type == EventType.GOAL:
                if e.team == self.home:
                    home += 1
                else:
                    away += 1
            if event_id is not None and e.id == event_id:
                break
        return home, away


class Statement(BaseModel):
    """One sentence of narration plus the structured claims it makes.

    `claims` is what the Verifier checks against the raw event data, so every
    sentence is traceable to evidence.
    """

    text: str
    event_ids: list[int] = Field(default_factory=list)
    claims: dict[str, Any] = Field(default_factory=dict)


class Narrative(BaseModel):
    statements: list[Statement]
    source: str = "template"  # "llm" or "template"
