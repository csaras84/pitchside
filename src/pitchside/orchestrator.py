"""Orchestrator: coordinates the agents through shared state, with handoffs and recovery.

  Analyst -> Narrator <-> Verifier (retry loop, deterministic fallback)
          -> Accessibility Adapter (one pass per profile) -> Translator

Every step is traced (agent, action, status, duration) so the pipeline is observable
and the UI can show *how* a recap was produced.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

from pydantic import BaseModel, Field

from .agents.accessibility import (
    AccessibleRecap,
    Profile,
    adapt,
    add_ssml,
)
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


class Orchestrator:
    def __init__(
        self,
        narrator: Narrator | None = None,
        translator: Translator | None = None,
        max_attempts: int = 3,
    ) -> None:
        self.narrator = narrator or Narrator()
        self.translator = translator or Translator()
        self.max_attempts = max_attempts

    @contextmanager
    def _span(self, trace: list[TraceEntry], agent: str, action: str) -> Iterator[TraceEntry]:
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

    def run(
        self,
        seed: int = 7,
        profiles: list[Profile] | None = None,
        language: str = "en",
    ) -> PipelineResult:
        profiles = profiles or list(Profile)
        trace: list[TraceEntry] = []

        with self._span(trace, "data", "generate synthetic match"):
            match = generate_match(seed)
        with self._span(trace, "analyst", "analyse events"):
            analysis = analyse(match)

        narrative: Narrative | None = None
        verification: Verification | None = None
        feedback: list[str] | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                with self._span(trace, "narrator", f"draft #{attempt}"):
                    draft = self.narrator.narrate(match, analysis, feedback)
            except Exception as exc:  # noqa: BLE001  LLM outage, bad JSON, ...: recover, don't crash
                feedback = [f"previous attempt failed: {exc}"]
                continue
            with self._span(trace, "verifier", f"check draft #{attempt}") as entry:
                result = verify(match, draft)
                if not result.passed:
                    entry.status = "rejected"
                    entry.detail = "; ".join(i.message for i in result.issues[:3])
            if result.passed:
                narrative, verification = draft, result
                break
            feedback = [i.message for i in result.issues]

        if narrative is None or verification is None:
            with self._span(trace, "narrator", "deterministic fallback") as entry:
                entry.status = "fallback"
                narrative = template_narrative(match, analysis)
            with self._span(trace, "verifier", "check fallback"):
                verification = verify(match, narrative)

        recaps: dict[str, AccessibleRecap] = {}
        translated = False
        for profile in profiles:
            with self._span(trace, "accessibility", f"adapt for {profile.value}"):
                recap = adapt(match, narrative, profile)
            if language != "en":
                with self._span(trace, "translator", f"{profile.value} -> {language}") as entry:
                    res = self.translator.translate([i.text for i in recap.items], language)
                    if res.translated:
                        for item, text in zip(recap.items, res.texts):
                            item.text = text
                        translated = True
                    else:
                        entry.status, entry.detail = "fallback", "kept English"
            if profile == Profile.BLIND:
                add_ssml(recap, language if translated else "en")
            recaps[profile.value] = recap

        return PipelineResult(
            match=match, analysis=analysis, narrative=narrative, verification=verification,
            recaps=recaps, language=language, translated=translated, trace=trace,
        )
