"""Depth (casual or analyst) and presentation (standard, deaf, blind, deafblind) are
independent settings: every one of the 8 combinations must be verified and usable."""

from pitchside.agents.accessibility import BRAILLE_CELLS, Profile
from pitchside.models import Depth
from pitchside.orchestrator import Orchestrator


def _run(depth, seed=7):
    return Orchestrator().run(seed=seed, depth=depth)


def test_all_eight_combinations_are_verified_and_non_empty():
    for depth in Depth:
        result = _run(depth)
        assert result.verification.passed and result.depth == depth.value
        assert set(result.recaps) == {p.value for p in Profile}
        for name, recap in result.recaps.items():
            assert recap.items, (depth, name)
            assert all(item.text.strip() for item in recap.items), (depth, name)


def test_deafblind_lines_never_exceed_the_braille_width_at_any_depth():
    for depth in Depth:
        for seed in (7, 11, 23):
            recap = _run(depth, seed).recaps["deafblind"]
            for item in recap.items:
                assert all(len(line) <= BRAILLE_CELLS for line in item.text.split("\n"))


def test_every_presentation_carries_the_reason_for_a_goal():
    for depth in Depth:
        result = _run(depth)
        goal = next(m for m in result.analysis.key_moments if m.kind == "goal")
        reason = goal.insights[0]
        state = reason.evidence["score_after"]
        for name in ("deaf", "deafblind"):
            item = next(i for i in result.recaps[name].items if i.event_id == goal.event_id)
            flat = " ".join(item.text.split())
            assert "Why it matters:" in flat, (depth, name)
            assert state in flat, (depth, name)
        for name in ("standard", "blind"):
            item = next(i for i in result.recaps[name].items if i.event_id == goal.event_id)
            assert state in item.text, (depth, name)  # the narrator's own sentence states it


def test_analyst_depth_says_more_than_casual():
    longer = 0
    for seed in range(20):
        casual = _run(Depth.CASUAL, seed).recaps["deaf"]
        analyst = _run(Depth.ANALYST, seed).recaps["deaf"]
        casual_chars = sum(len(i.text) for i in casual.items)
        analyst_chars = sum(len(i.text) for i in analyst.items)
        assert analyst_chars >= casual_chars
        longer += analyst_chars > casual_chars
    assert longer > 0
