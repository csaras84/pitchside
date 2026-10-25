"""The Verifier on explanations: reasons must exist, say what they claim, and be right."""

from pitchside.agents.analyst import analyse
from pitchside.agents.narrator import template_narrative
from pitchside.agents.verifier import figures_match, shows_figure, verify
from pitchside.data.generator import generate_match
from pitchside.models import Depth, Statement


def _first_goal_statement(narrative):
    return next(i for i, s in enumerate(narrative.statements) if "score" in s.claims)


def test_template_narratives_pass_at_both_depths():
    for seed in (7, 11, 23):
        match = generate_match(seed)
        for depth in Depth:
            narrative = template_narrative(match, analyse(match), depth)
            result = verify(match, narrative, depth)
            assert result.passed, (seed, depth, result.issues)


def test_analyst_depth_explains_more_than_casual():
    totals = {Depth.CASUAL: 0, Depth.ANALYST: 0}
    for seed in range(40):
        match = generate_match(seed)
        for depth in Depth:
            narrative = template_narrative(match, analyse(match), depth)
            totals[depth] += sum(len(s.claims.get("why", [])) for s in narrative.statements)
    assert totals[Depth.ANALYST] > totals[Depth.CASUAL] > 0


def test_analyst_statements_carry_their_evidence():
    match = generate_match(7)
    narrative = template_narrative(match, analyse(match), Depth.ANALYST)
    goal = narrative.statements[_first_goal_statement(narrative)]
    assert goal.claims["evidence"][goal.claims["why"][0]]["score_after"] == goal.claims["score"]


def test_verifier_rejects_a_reason_the_events_do_not_support():
    match = generate_match(7)
    narrative = template_narrative(match, analyse(match))
    idx = _first_goal_statement(narrative)
    s = narrative.statements[idx]
    narrative.statements[idx] = Statement(
        text=s.text, event_ids=s.event_ids, claims={**s.claims, "why": ["would_have_levelled"]}
    )
    result = verify(match, narrative)
    assert not result.passed and "why" in {i.field for i in result.issues}


def test_verifier_rejects_wrong_evidence_figures():
    match = generate_match(7)
    narrative = template_narrative(match, analyse(match), Depth.ANALYST)
    idx = _first_goal_statement(narrative)
    s = narrative.statements[idx]
    code = s.claims["why"][0]
    bad = {**s.claims["evidence"], code: {"score_after": "9-9"}}
    narrative.statements[idx] = Statement(
        text=s.text, event_ids=s.event_ids, claims={**s.claims, "evidence": bad}
    )
    result = verify(match, narrative, Depth.ANALYST)
    assert not result.passed and "evidence" in {i.field for i in result.issues}


def test_verifier_rejects_prose_that_contradicts_the_reason():
    match = generate_match(7)
    narrative = template_narrative(match, analyse(match))
    idx = _first_goal_statement(narrative)
    s = narrative.statements[idx]
    event = match.event_by_id(s.event_ids[0])
    neutral = f"Minute {event.minute}: {event.player} scores for {event.team}. It is {s.claims['score']}."
    narrative.statements[idx] = Statement(text=neutral, event_ids=s.event_ids, claims=s.claims)
    result = verify(match, narrative)
    assert not result.passed and "text" in {i.field for i in result.issues}


def test_verifier_requires_the_explanation_the_depth_promises():
    match = generate_match(7)
    plain = template_narrative(match, analyse(match))
    for s in plain.statements:  # strip every explanation
        s.claims.pop("why", None)
        s.claims.pop("evidence", None)
    assert verify(match, plain).passed  # fine when no depth is demanded
    missing = verify(match, plain, Depth.CASUAL)
    assert not missing.passed and "why" in {i.field for i in missing.issues}

    casual = template_narrative(match, analyse(match), Depth.CASUAL)
    analyst = template_narrative(match, analyse(match), Depth.ANALYST)

    def total(narrative):
        return sum(len(s.claims.get("why", [])) for s in narrative.statements)

    if total(analyst) > total(casual):  # a casual story is not enough for an analyst
        assert not verify(match, casual, Depth.ANALYST).passed


def test_figure_helpers_are_strict_about_numbers():
    assert shows_figure("attacking threat 12.0 to 3.5", 12.0)
    assert shows_figure("attacking threat 12 to 3.5", 12.0)
    assert not shows_figure("attacking threat 12.5 to 3.5", 12.0)
    assert not shows_figure("attacking threat 112.0", 12.0)
    assert shows_figure("it is 1-0", "1-0", "score_after")
    assert not shows_figure("it is 0-1", "1-0", "score_after")
    assert figures_match(0.31, 0.3) and not figures_match(0.5, 0.3)
    assert figures_match("1-0", "1-0") and not figures_match("1-0", "0-1")
