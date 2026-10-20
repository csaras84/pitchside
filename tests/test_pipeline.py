"""Orchestration tests: failure recovery and the HTTP API."""

import json

from pitchside.agents.narrator import Narrator
from pitchside.agents.translator import TranslationResult, Translator
from pitchside.orchestrator import Orchestrator


class ScriptedLLM:
    """Fake LLM that returns scripted responses, then repeats the last one."""

    available = True

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0
        self.last_user = ""

    def complete_json(self, system, user):
        self.last_user = user
        r = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        if isinstance(r, Exception):
            raise r
        return r


def _good_draft(orchestrator_seed=7):
    from pitchside.agents.analyst import analyse
    from pitchside.agents.narrator import template_narrative
    from pitchside.data.generator import generate_match

    m = generate_match(orchestrator_seed)
    return json.loads(template_narrative(m, analyse(m)).model_dump_json())


def _lying_draft():
    draft = _good_draft()
    for s in draft["statements"]:
        if "score" in s["claims"]:
            s["claims"]["score"] = "7-7"
            break
    return draft


def test_offline_pipeline_runs_without_credentials():
    result = Orchestrator().run(seed=7)
    assert result.verification.passed
    assert result.narrative.source == "template"
    assert set(result.recaps) == {"standard", "deaf", "blind", "deafblind"}
    assert [t.agent for t in result.trace][:2] == ["data", "analyst"]


def test_verifier_rejects_lying_llm_then_retry_succeeds():
    llm = ScriptedLLM(_lying_draft(), _good_draft())
    result = Orchestrator(narrator=Narrator(llm)).run(seed=7)
    assert result.verification.passed
    assert result.narrative.source == "llm"
    assert llm.calls == 2
    assert "Verifier issues" in llm.last_user  # feedback was handed back to the Narrator
    statuses = [t.status for t in result.trace if t.agent == "verifier"]
    assert statuses == ["rejected", "ok"]


def test_falls_back_to_template_when_llm_keeps_failing():
    llm = ScriptedLLM(RuntimeError("service unavailable"))
    result = Orchestrator(narrator=Narrator(llm), max_attempts=2).run(seed=7)
    assert result.verification.passed
    assert result.narrative.source == "template"
    assert any(t.status == "fallback" for t in result.trace)


def test_falls_back_when_llm_returns_garbage_json():
    llm = ScriptedLLM({"unexpected": "shape"})
    result = Orchestrator(narrator=Narrator(llm), max_attempts=2).run(seed=7)
    assert result.narrative.source == "template" and result.verification.passed


def test_translation_applied_when_service_works():
    class FakeTranslator(Translator):
        @property
        def available(self):
            return True

        def translate(self, texts, to):
            return TranslationResult([f"[{to}] {t}" for t in texts], True)

    result = Orchestrator(translator=FakeTranslator()).run(seed=7, language="es")
    assert result.translated
    assert result.recaps["standard"].items[0].text.startswith("[es] ")
    assert "es-ES-ElviraNeural" in result.recaps["blind"].items[0].ssml


def test_translation_falls_back_to_english_without_service():
    result = Orchestrator(translator=Translator(key=None, region=None)).run(seed=7, language="fr")
    assert not result.translated
    assert any(t.agent == "translator" and t.status == "fallback" for t in result.trace)

