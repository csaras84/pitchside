"""Simulated live replay: the match as it stood at a series of checkpoint minutes.

Each frame is a full pipeline run on only the events up to that minute, so nothing in it can
refer to the future. Frames are written by the built-in (offline) agents, which keeps a replay
free to play; every frame still goes through the Verifier like any other recap.
"""

from __future__ import annotations

from pydantic import BaseModel

from .agents.accessibility import Profile
from .data.generator import generate_match
from .models import Depth, EventType, Match
from .orchestrator import Orchestrator, PipelineResult

STEP = 10  # a frame every ten minutes, plus one right after each goal or red card


class Replay(BaseModel):
    minutes: list[int]
    frames: list[PipelineResult]


def checkpoints(match: Match) -> list[int]:
    """Minutes at which the replay pauses: every STEP minutes, after each goal or red card, and full time."""
    marks = set(range(STEP, 90, STEP)) | {90}
    marks |= {
        e.minute
        for e in match.events
        if e.type in (EventType.GOAL, EventType.RED_CARD) and 0 < e.minute < 90
    }
    return sorted(marks)


def build_replay(
    orchestrator: Orchestrator,
    seed: int = 7,
    profiles: list[Profile] | None = None,
    depth: Depth = Depth.CASUAL,
    archetype: str | None = None,
) -> Replay:
    minutes = checkpoints(generate_match(seed, archetype=archetype))
    frames = [
        orchestrator.run(
            seed=seed, profiles=profiles, depth=depth, archetype=archetype, up_to_minute=m
        )
        for m in minutes
    ]
    return Replay(minutes=minutes, frames=frames)
