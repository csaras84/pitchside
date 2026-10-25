"""Plain-Python orchestrator: coordinates the agents through shared state, with recovery.

  Analyst -> Narrator <-> Verifier (retry loop, deterministic fallback)
          -> Accessibility Adapter (one pass per profile) -> Translator

Every step is traced (agent, action, status, duration) so the pipeline is observable
and the UI can show *how* a recap was produced. The same steps also run inside the
Microsoft Agent Framework workflow (see af_workflow.py).
"""

from __future__ import annotations

from .agents.accessibility import Profile
from .agents.narrator import Narrator
from .agents.translator import Translator
from .models import Depth
from .pipeline_steps import (
    PipelineResult,
    RunState,
    TraceEntry,
    build_result,
    step_adapt,
    step_analyse,
    step_fallback,
    step_narrate,
    step_verify,
)

__all__ = ["Orchestrator", "PipelineResult", "TraceEntry"]


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

    def run(
        self,
        seed: int = 7,
        profiles: list[Profile] | None = None,
        language: str = "en",
        depth: Depth = Depth.CASUAL,
        archetype: str | None = None,
        up_to_minute: int | None = None,
        fault: str | None = None,
    ) -> PipelineResult:
        state = RunState(
            seed=seed,
            profiles=profiles or list(Profile),
            language=language,
            depth=Depth(depth),
            archetype=archetype,
            up_to_minute=up_to_minute,
            fault=fault,
            max_attempts=self.max_attempts,
        )
        step_analyse(state)
        for _ in range(state.max_attempts):
            step_narrate(state, self.narrator)
            if state.draft is None:  # the narrator failed outright: try again
                continue
            step_verify(state)
            if state.verified:
                break
        if not state.verified:
            step_fallback(state)
        step_adapt(state, self.translator)
        return build_result(state)
