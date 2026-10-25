"""Agent Framework engine tests. Skipped automatically if the package is not installed."""

from types import SimpleNamespace

import pytest

pytest.importorskip("agent_framework")

from pitchside.af_workflow import AgentFrameworkOrchestrator, AgentNarrator
from pitchside.agents.analyst import analyse
from pitchside.agents.narrator import template_narrative
from pitchside.data.generator import generate_match
from pitchside.orchestrator import Orchestrator


class ScriptedNarrator:
    """Returns scripted drafts (or raises), then repeats the last one."""

    def __init__(self, *items):
        self.items = list(items)
        self.calls = 0
        self.feedback_seen = []

    async def narrate(self, match, analysis, feedback=None, depth="casual"):
        self.feedback_seen.append(feedback)
        item = self.items[min(self.calls, len(self.items) - 1)]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        return item


def _good():
    match = generate_match(7)
    return template_narrative(match, analyse(match))


def _lying():
    draft = _good()
    for s in draft.statements:
        if "score" in s.claims:
            s.claims["score"] = "7-7"
            break
    return draft


def _verifier_statuses(result):
    return [t.status for t in result.trace if t.agent == "verifier"]


def test_workflow_runs_offline_and_matches_the_plain_engine():
    narrator = AgentNarrator(SimpleNamespace(available=False))
    af = AgentFrameworkOrchestrator(narrator=narrator).run(seed=7)
    plain = Orchestrator().run(seed=7)
    assert af.verification.passed
    assert af.analysis.final_score == plain.analysis.final_score
    assert set(af.recaps) == set(plain.recaps)
    for name in plain.recaps:
        assert [i.text for i in af.recaps[name].items] == [i.text for i in plain.recaps[name].items]


def test_verifier_rejects_a_lying_draft_and_the_retry_is_accepted():
    narrator = ScriptedNarrator(_lying(), _good())
    result = AgentFrameworkOrchestrator(narrator=narrator).run(seed=7)
    assert _verifier_statuses(result) == ["rejected", "ok"]
    assert narrator.calls == 2
    assert narrator.feedback_seen[0] is None and narrator.feedback_seen[1]
    assert result.verification.passed


def test_falls_back_after_every_attempt_is_rejected():
    narrator = ScriptedNarrator(_lying())
    result = AgentFrameworkOrchestrator(narrator=narrator).run(seed=7)
    assert narrator.calls == 3
    assert _verifier_statuses(result) == ["rejected", "rejected", "rejected", "ok"]
    assert any(t.status == "fallback" for t in result.trace)
    assert result.verification.passed


def test_falls_back_when_the_model_keeps_failing():
    narrator = ScriptedNarrator(RuntimeError("service unavailable"))
    result = AgentFrameworkOrchestrator(narrator=narrator).run(seed=7)
    assert narrator.calls == 3
    assert any(t.agent == "narrator" and t.status == "error" for t in result.trace)
    assert any(t.status == "fallback" for t in result.trace)
    assert result.verification.passed
