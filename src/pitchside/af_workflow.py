"""Microsoft Agent Framework engine.

The same pipeline as the plain orchestrator, expressed as an Agent Framework workflow:

  analyst -> narrator_1 -> verifier_1 -+-> (verified) ---------------> adapt -> finish
                |                      +-> narrator_2 -> verifier_2 -+-> adapt
                +-> (narrator error) -----> narrator_2 ...           +-> narrator_3 ...
                                                                          |
                                         (last attempt failed) -> fallback -> adapt

* The Narrator is a real framework Agent (`as_agent`) backed by the Foundry deployment.
* The Verifier routes with conditional edges; nothing reaches `adapt` unless it passed.
* Retry attempts are unrolled into separate nodes instead of a loop-back edge.
* After the last failed attempt a deterministic fallback narrator takes over.

NOTE: this module deliberately does not use `from __future__ import annotations`.
The framework reads the type hints of executor handlers at runtime, so they must be
real classes and not strings.
"""

import asyncio
from typing import Any, Never

from agent_framework import WorkflowBuilder, WorkflowContext, executor

from .agents.accessibility import Profile
from .agents.narrator import (
    SYSTEM_PROMPT,
    build_user_prompt,
    extract_json,
    parse_narrative,
    template_narrative,
)
from .agents.translator import Translator
from .llm import LLMClient
from .models import Match, Narrative
from .pipeline_steps import (
    PipelineResult,
    RunState,
    build_result,
    record_narration_failure,
    span,
    start_attempt,
    step_adapt,
    step_analyse,
    step_fallback,
    step_verify,
)


class AgentNarrator:
    """Narrator backed by a framework Agent that talks to the Foundry deployment.

    With no credentials it falls back to the deterministic template, like the plain engine.
    """

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()
        self._agent: Any = None

    @property
    def available(self) -> bool:
        return self.llm.available

    def _get_agent(self) -> Any:
        if self._agent is None:
            from agent_framework.openai import OpenAIChatCompletionClient

            settings = {"api_key": self.llm.api_key, "base_url": self.llm.base_url}
            try:
                client = OpenAIChatCompletionClient(model=self.llm.deployment, **settings)
            except TypeError:  # older releases named this argument model_id
                client = OpenAIChatCompletionClient(model_id=self.llm.deployment, **settings)
            self._agent = client.as_agent(instructions=SYSTEM_PROMPT, name="narrator")
        return self._agent

    async def narrate(
        self, match: Match, analysis: Any, feedback: list[str] | None = None
    ) -> Narrative:
        if not self.available:
            return template_narrative(match, analysis)
        result = await self._get_agent().run(build_user_prompt(match, analysis, feedback))
        text = getattr(result, "text", None) or str(result)
        return parse_narrative(extract_json(text), source="llm")


# Edge conditions: each receives the RunState produced by the upstream executor.
def _has_draft(message: Any) -> bool:
    return isinstance(message, RunState) and message.draft is not None


def _no_draft(message: Any) -> bool:
    return isinstance(message, RunState) and message.draft is None


def _is_verified(message: Any) -> bool:
    return isinstance(message, RunState) and message.verified


def _not_verified(message: Any) -> bool:
    return isinstance(message, RunState) and not message.verified


def build_workflow(narrator: Any, translator: Translator, max_attempts: int = 3) -> Any:
    @executor(id="analyst")
    async def analyst(state: RunState, ctx: WorkflowContext[RunState]) -> None:
        step_analyse(state)
        await ctx.send_message(state)

    def make_narrator(n: int) -> Any:
        @executor(id=f"narrator_{n}")
        async def narrate(state: RunState, ctx: WorkflowContext[RunState]) -> None:
            action = start_attempt(state)
            try:
                with span(state.trace, "narrator", action):
                    state.draft = await narrator.narrate(
                        state.match, state.analysis, state.feedback or None
                    )
            except Exception as exc:  # noqa: BLE001  model outage, bad JSON: recover, don't crash
                record_narration_failure(state, exc)
            await ctx.send_message(state)

        return narrate

    def make_verifier(n: int) -> Any:
        @executor(id=f"verifier_{n}")
        async def check(state: RunState, ctx: WorkflowContext[RunState]) -> None:
            step_verify(state)
            await ctx.send_message(state)

        return check

    @executor(id="fallback")
    async def fallback(state: RunState, ctx: WorkflowContext[RunState]) -> None:
        step_fallback(state)
        await ctx.send_message(state)

    @executor(id="adapt")
    async def adapt_and_translate(state: RunState, ctx: WorkflowContext[RunState]) -> None:
        # Translation is a blocking HTTP call, so keep it off the event loop.
        await asyncio.to_thread(step_adapt, state, translator)
        await ctx.send_message(state)

    @executor(id="finish")
    async def finish(state: RunState, ctx: WorkflowContext[Never, PipelineResult]) -> None:
        await ctx.yield_output(build_result(state))

    narrators = [make_narrator(n) for n in range(1, max_attempts + 1)]
    verifiers = [make_verifier(n) for n in range(1, max_attempts + 1)]

    builder = WorkflowBuilder(start_executor=analyst)
    builder.add_edge(analyst, narrators[0])
    for i in range(max_attempts):
        after_failure = narrators[i + 1] if i + 1 < max_attempts else fallback
        builder.add_edge(narrators[i], verifiers[i], condition=_has_draft)
        builder.add_edge(narrators[i], after_failure, condition=_no_draft)
        builder.add_edge(verifiers[i], adapt_and_translate, condition=_is_verified)
        builder.add_edge(verifiers[i], after_failure, condition=_not_verified)
    builder.add_edge(fallback, adapt_and_translate)
    builder.add_edge(adapt_and_translate, finish)
    return builder.build()


class AgentFrameworkOrchestrator:
    """Runs the recap pipeline as an Agent Framework workflow."""

    def __init__(
        self,
        narrator: Any = None,
        translator: Translator | None = None,
        max_attempts: int = 3,
    ) -> None:
        self.narrator = narrator or AgentNarrator()
        self.translator = translator or Translator()
        self.max_attempts = max_attempts

    async def arun(
        self,
        seed: int = 7,
        profiles: list[Profile] | None = None,
        language: str = "en",
    ) -> PipelineResult:
        workflow = build_workflow(self.narrator, self.translator, self.max_attempts)
        state = RunState(
            seed=seed,
            profiles=profiles or list(Profile),
            language=language,
            max_attempts=self.max_attempts,
        )
        events = await workflow.run(state)
        outputs = events.get_outputs()
        if not outputs:
            raise RuntimeError("the workflow finished without producing a result")
        return outputs[0]

    def run(
        self,
        seed: int = 7,
        profiles: list[Profile] | None = None,
        language: str = "en",
    ) -> PipelineResult:
        """Synchronous wrapper (call from a thread with no running event loop)."""
        return asyncio.run(self.arun(seed, profiles, language))
