"""The Verifier demo: injected faults are caught, labelled, and never reach the reader."""

import pytest

from pitchside.agents.analyst import analyse
from pitchside.agents.narrator import Narrator, template_narrative
from pitchside.agents.verifier import verify
from pitchside.data.generator import ARCHETYPES, generate_match
from pitchside.faults import FAULTS, inject
from pitchside.models import Depth
from pitchside.orchestrator import Orchestrator

OFFLINE = Orchestrator(narrator=Narrator(None))
STORIES = (None, *ARCHETYPES)


def test_every_injected_fault_is_caught_by_the_verifier():
    caught = 0
    for archetype in STORIES:
        for seed in range(6):
            match = generate_match(seed, archetype=archetype)
            if not any(e.type.value == "goal" for e in match.events):
                continue  # a goalless match has no score claim to corrupt
            for depth in Depth:
                clean = template_narrative(match, analyse(match), depth)
                assert verify(match, clean, depth).passed
                for fault in FAULTS:
                    bad, what = inject(clean, fault)
                    assert bad != clean and what
                    result = verify(match, bad, depth)
                    assert not result.passed, (archetype, seed, depth, fault, what)
                    caught += 1
    assert caught > 50


def test_injection_does_not_touch_the_original_draft():
    match = generate_match(3, archetype="red_card_swing")
    clean = template_narrative(match, analyse(match), Depth.CASUAL)
    snapshot = clean.model_copy(deep=True)
    inject(clean, "wrong_minute")
    assert clean == snapshot


def test_unknown_fault_is_refused():
    match = generate_match(3, archetype="red_card_swing")
    with pytest.raises(ValueError):
        inject(template_narrative(match, analyse(match)), "gremlins")


def test_pipeline_shows_a_labelled_rejection_then_a_clean_retry():
    for fault in FAULTS:
        for archetype in ("red_card_swing", "late_comeback"):
            result = OFFLINE.run(seed=3, archetype=archetype, depth=Depth.ANALYST, fault=fault)
            steps = [(t.agent, t.status) for t in result.trace]
            assert ("demo", "injected") in steps
            injected = next(t for t in result.trace if t.agent == "demo")
            assert injected.detail.startswith("INJECTED FAULT")
            rejected = next(t for t in result.trace if t.status == "rejected")
            assert rejected.detail  # the reason is recorded
            assert steps.index(("demo", "injected")) < steps.index(("verifier", "rejected"))
            assert result.verification.passed
            # the corrupted draft never reaches the reader: the accepted recap equals the clean one
            clean = OFFLINE.run(seed=3, archetype=archetype, depth=Depth.ANALYST)
            assert result.narrative == clean.narrative
            assert not any(t.agent == "demo" for t in clean.trace)
