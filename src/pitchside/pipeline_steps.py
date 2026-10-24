"""Pipeline steps shared by both engines.

The plain-Python `Orchestrator` and the Microsoft Agent Framework workflow call exactly
these functions, so both engines behave the same and are traced the same way.

  analyse -> narrate -> verify (retry, then deterministic fallback) -> adapt/translate
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from .agents.accessibility import AccessibleRecap, Profile, adapt, add_ssml
from .agents.analyst import Analysis, analyse
from .agents.narrator import Narrator, template_narrative
from .agents.translator import Translator
from .agents.verifier import Verification, verify
from .data.generator import generate_match
from .models import Match, Narrative


class TraceEntry(BaseModel):
    agent: str
    action: str
    status: str = "ok"  # ok | rejected | error | fallback
    ms: float = 0.0
    detail: str = ""


class PipelineResult(BaseModel):
    match: Match
    analysis: Analysis
    narrative: Narrative
    verification: Verification
    recaps: dict[str, AccessibleRecap]
    language: str = "en"
    translated: bool = False
    trace: list[TraceEntry] = Field(default_factory=list)


@contextmanager
def span(trace: list[TraceEntry], agent: str, action: str) -> Iterator[TraceEntry]:
    """Time a step and record it (agent, action, status, milliseconds) in the trace."""
    entry = TraceEntry(agent=agent, action=action)
    start = time.perf_counter()
    try:
        yield entry
    except Exception as exc:
        entry.status, entry.detail = "error", str(exc)
        raise
    finally:
        entry.ms = round((time.perf_counter() - start) * 1000, 2)
        trace.append(entry)


@dataclass
class RunState:
    """Shared state handed from step to step (and from executor to executor)."""

    seed: int = 7
    profiles: list[Profile] = field(default_factory=lambda: list(Profile))
    language: str = "en"
    max_attempts: int = 3
    attempt: int = 0
    match: Match | None = None
    analysis: Analysis | None = None
    draft: Narrative | None = None  # latest Narrator output, not yet trusted
    narrative: Narrative | None = None  # accepted only after the Verifier passes it
    verification: Verification | None = None
    feedback: list[str] = field(default_factory=list)
    recaps: dict[str, AccessibleRecap] = field(default_factory=dict)
    translated: bool = False
    trace: list[TraceEntry] = field(default_factory=list)

    @property
    def verified(self) -> bool:
        return (
            self.narrative is not None
            and self.verification is not None
            and self.verification.passed
        )


def step_analyse(state: RunState) -> None:
    with span(state.trace, "data", "generate synthetic match"):
        state.match = generate_match(state.seed)
    with span(state.trace, "analyst", "analyse events"):
        state.analysis = analyse(state.match)


def start_attempt(state: RunState) -> str:
    """Begin a narration attempt; returns the label used in the trace."""
    state.attempt += 1
    state.draft = None
    return f"draft #{state.attempt}"


def record_narration_failure(state: RunState, exc: Exception) -> None:
    state.feedback = [f"previous attempt failed: {exc}"]


def step_narrate(state: RunState, narrator: Narrator) -> None:
    action = start_attempt(state)
    try:
        with span(state.trace, "narrator", action):
            state.draft = narrator.narrate(state.match, state.analysis, state.feedback or None)
    except Exception as exc:  # noqa: BLE001  LLM outage, bad JSON, ...: recover, don't crash
        record_narration_failure(state, exc)


def step_verify(state: RunState) -> None:
    draft = state.draft
    with span(state.trace, "verifier", f"check draft #{state.attempt}") as entry:
        result = verify(state.match, draft)
        if not result.passed:
            entry.status = "rejected"
            entry.detail = "; ".join(i.message for i in result.issues[:3])
    state.verification = result
    if result.passed:
        state.narrative = draft
    else:
        state.feedback = [i.message for i in result.issues]


def step_fallback(state: RunState) -> None:
    with span(state.trace, "narrator", "deterministic fallback") as entry:
        entry.status = "fallback"
        state.narrative = template_narrative(state.match, state.analysis)
    with span(state.trace, "verifier", "check fallback"):
        state.verification = verify(state.match, state.narrative)


def step_adapt(state: RunState, translator: Translator) -> None:
    for profile in state.profiles:
        with span(state.trace, "accessibility", f"adapt for {profile.value}"):
            recap = adapt(state.match, state.narrative, profile)
        if state.language != "en":
            action = f"{profile.value} -> {state.language}"
            with span(state.trace, "translator", action) as entry:
                res = translator.translate([i.text for i in recap.items], state.language)
                if res.translated:
                    for item, text in zip(recap.items, res.texts, strict=True):
                        item.text = text
                    state.translated = True
                else:
                    entry.status, entry.detail = "fallback", "kept English"
        if profile == Profile.BLIND:
            add_ssml(recap, state.language if state.translated else "en")
        state.recaps[profile.value] = recap


def build_result(state: RunState) -> PipelineResult:
    return PipelineResult(
        match=state.match,
        analysis=state.analysis,
        narrative=state.narrative,
        verification=state.verification,
        recaps=state.recaps,
        language=state.language,
        translated=state.translated,
        trace=state.trace,
    )
