"""Story archetypes, the red card, match-level reasons, and the planted-storyline check."""

import pytest

from pitchside.agents.accessibility import BRAILLE_CELLS, Profile, adapt
from pitchside.agents.analyst import analyse, insights_for, match_insights
from pitchside.agents.narrator import template_narrative
from pitchside.agents.verifier import verify
from pitchside.data.generator import ARCHETYPES, generate_match
from pitchside.models import Depth, EventType, Statement
from pitchside.orchestrator import Orchestrator
from pitchside.storycheck import check_planted

SEEDS = range(25)


def _goals(match, team):
    return [e for e in match.events if e.type == EventType.GOAL and e.team == team]


def test_default_matches_are_unchanged_and_have_no_planted_story():
    match = generate_match(7)
    assert match.planted == []
    assert not any(e.type == EventType.RED_CARD for e in match.events)
    assert match.score_after() == (0, 2)  # the match the UI and docs call "Match 7"


def test_archetype_matches_are_deterministic_and_validated():
    for archetype in ARCHETYPES:
        assert generate_match(3, archetype=archetype) == generate_match(3, archetype=archetype)
        assert generate_match(3, archetype=archetype) != generate_match(4, archetype=archetype)
    with pytest.raises(ValueError):
        generate_match(3, archetype="not_a_story")


def test_red_card_swing_script():
    for seed in SEEDS:
        match = generate_match(seed, archetype="red_card_swing")
        plant = match.planted[0]
        red = next(e for e in match.events if e.type == EventType.RED_CARD)
        assert (red.team, red.minute) == (plant.team, plant.minute)
        other = match.away if plant.team == match.home else match.home
        assert not _goals(match, plant.team)  # the side with ten men never scores
        assert all(g.minute > red.minute for g in _goals(match, other))
        assert _goals(match, other)


def test_late_comeback_script():
    for seed in SEEDS:
        match = generate_match(seed, archetype="late_comeback")
        team = match.planted[0].team
        other = match.away if team == match.home else match.home
        assert len(_goals(match, other)) == 2 and len(_goals(match, team)) == 3
        assert [g.minute for g in _goals(match, other)] == sorted(g.minute for g in _goals(match, other))
        assert max(g.minute for g in _goals(match, other)) < min(g.minute for g in _goals(match, team))


def test_dominant_wasteful_script():
    for seed in SEEDS:
        match = generate_match(seed, archetype="dominant_wasteful")
        team = match.planted[0].team
        other = match.away if team == match.home else match.home
        xg = {t: sum(e.xg for e in match.events if e.team == t) for t in (team, other)}
        assert xg[team] - xg[other] >= 1.4
        assert not _goals(match, team) and len(_goals(match, other)) == 1


def test_the_analyst_finds_every_planted_story_from_the_events_alone():
    for archetype in ARCHETYPES:
        for seed in SEEDS:
            match = generate_match(seed, archetype=archetype)
            (check,) = check_planted(match, analyse(match))
            assert check.recovered, (archetype, seed, check.found)


def test_the_check_is_not_vacuous():
    """Against the analysis of an unrelated match it must mostly say 'not found'."""
    hits = total = 0
    for archetype in ARCHETYPES:
        for seed in range(30):
            story = generate_match(seed, archetype=archetype)
            unrelated = analyse(generate_match(seed))
            hits += check_planted(story, unrelated)[0].recovered
            total += 1
    assert hits / total < 0.10


def test_no_check_for_a_match_that_is_still_being_played():
    match = generate_match(3, archetype="red_card_swing")
    assert check_planted(match.until(30), analyse(match.until(30))) == []


def test_red_card_reasons_and_rendering():
    match = generate_match(3, archetype="red_card_swing")
    red = next(e for e in match.events if e.type == EventType.RED_CARD)
    found = {i.code: i for i in insights_for(match, red)}
    assert found["sent_off"].evidence == {"players_left": 10}
    assert "10 players" in found["sent_off"].text
    narrative = template_narrative(match, analyse(match))
    deaf = adapt(match, narrative, Profile.DEAF).items
    item = next(i for i in deaf if i.event_id == red.id)
    assert "red card" in item.sound_cue and item.haptic and "sent off" in item.text
    for item in adapt(match, narrative, Profile.DEAFBLIND).items:
        assert all(len(line) <= BRAILLE_CELLS for line in item.text.split("\n"))


def test_wasted_dominance_is_a_match_level_reason_and_needs_a_real_gap():
    match = generate_match(3, archetype="dominant_wasteful")
    (reason,) = match_insights(match)
    assert reason.code == "wasted_dominance" and reason.evidence["xg_team"] > reason.evidence["xg_other"]
    assert match_insights(match.until(60)) == []  # nothing to say until the match is over
    assert match_insights(generate_match(7)) == []  # an ordinary 0-2 has no such story


def test_template_narratives_for_every_story_pass_at_both_depths():
    for archetype in ARCHETYPES:
        for seed in range(8):
            match = generate_match(seed, archetype=archetype)
            for depth in Depth:
                narrative = template_narrative(match, analyse(match), depth)
                result = verify(match, narrative, depth)
                assert result.passed, (archetype, seed, depth, result.issues)


def test_verifier_checks_match_level_reasons():
    match = generate_match(3, archetype="dominant_wasteful")
    good = template_narrative(match, analyse(match), Depth.ANALYST)
    idx = next(i for i, s in enumerate(good.statements) if "match_why" in s.claims)

    unsupported = template_narrative(match, analyse(match), Depth.ANALYST)
    s = unsupported.statements[idx]
    unsupported.statements[idx] = Statement(text=s.text, claims={**s.claims, "match_why": ["comeback"]})
    assert "match_why" in {i.field for i in verify(match, unsupported, Depth.ANALYST).issues}

    wrong_figures = template_narrative(match, analyse(match), Depth.ANALYST)
    s = wrong_figures.statements[idx]
    code = s.claims["match_why"][0]
    bad = {code: {**s.claims["evidence"][code], "xg_team": 9.99}}
    wrong_figures.statements[idx] = Statement(text=s.text, claims={**s.claims, "evidence": bad})
    assert "evidence" in {i.field for i in verify(match, wrong_figures, Depth.ANALYST).issues}

    omitted = template_narrative(match, analyse(match), Depth.CASUAL)
    del omitted.statements[idx]
    missing = verify(match, omitted, Depth.CASUAL)
    assert not missing.passed and "match_why" in {i.field for i in missing.issues}


def test_full_pipeline_on_a_story_match():
    for archetype in ARCHETYPES:
        result = Orchestrator().run(seed=3, depth=Depth.ANALYST, archetype=archetype)
        assert result.verification.passed
        assert result.story and all(c.recovered for c in result.story)
        assert set(result.recaps) == {p.value for p in Profile}
        if archetype == "dominant_wasteful":
            assert any("match_why" in s.claims for s in result.narrative.statements)
