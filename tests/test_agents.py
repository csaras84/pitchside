from pitchside.agents.accessibility import (
    BRAILLE_CELLS,
    Profile,
    adapt,
    add_ssml,
    describe_position,
    threat_tone_hz,
)
from pitchside.agents.analyst import analyse
from pitchside.agents.narrator import template_narrative
from pitchside.agents.verifier import verify
from pitchside.data.generator import generate_match
from pitchside.models import EventType, Statement


def test_generator_is_deterministic_and_has_goals():
    a, b = generate_match(7), generate_match(7)
    assert a == b
    assert generate_match(8) != a
    assert sum(e.type == EventType.GOAL for e in a.events) >= 2
    assert [e.minute for e in a.events] == sorted(e.minute for e in a.events)


def test_analyst_matches_raw_data():
    match = generate_match(7)
    analysis = analyse(match)
    h, a = match.score_after()
    assert analysis.final_score == f"{h}-{a}"
    goal_moments = [m for m in analysis.key_moments if m.kind == "goal"]
    assert len(goal_moments) == sum(e.type == EventType.GOAL for e in match.events)
    assert len(analysis.momentum) == 6


def test_template_narrative_passes_verification():
    match = generate_match(7)
    narrative = template_narrative(match, analyse(match))
    result = verify(match, narrative)
    assert result.passed, result.issues
    assert result.checked >= 2


def test_verifier_catches_wrong_player_minute_and_score():
    match = generate_match(7)
    narrative = template_narrative(match, analyse(match))
    idx = next(i for i, s in enumerate(narrative.statements) if "score" in s.claims)
    s = narrative.statements[idx]
    event = match.event_by_id(s.event_ids[0])

    narrative.statements[idx] = Statement(
        text=s.text.replace(event.player, "Nobody Real"),
        event_ids=s.event_ids,
        claims={**s.claims, "player": "Nobody Real", "minute": event.minute + 7, "score": "9-9"},
    )
    result = verify(match, narrative)
    assert not result.passed
    fields = {i.field for i in result.issues}
    assert {"player", "minute", "score"} <= fields


def test_verifier_flags_claims_without_evidence_and_missing_events():
    match = generate_match(7)
    bad = template_narrative(match, analyse(match))
    bad.statements.append(Statement(text="Someone scored.", claims={"minute": 3}))
    bad.statements.append(Statement(text="Ghost event.", event_ids=[9999], claims={}))
    result = verify(match, bad)
    assert not result.passed
    assert {i.field for i in result.issues} >= {"event_ids"}


def test_deaf_profile_has_cues_and_haptics_for_goals():
    match = generate_match(7)
    narrative = template_narrative(match, analyse(match))
    recap = adapt(match, narrative, Profile.DEAF)
    goal_items = [i for i in recap.items if i.sound_cue == "[crowd erupts]"]
    assert goal_items
    assert all(i.haptic and i.text.startswith("[crowd erupts]") for i in goal_items)


def test_blind_profile_has_spatial_description_and_ssml():
    match = generate_match(7)
    narrative = template_narrative(match, analyse(match))
    recap = adapt(match, narrative, Profile.BLIND)
    add_ssml(recap, "es")
    spatial = [i for i in recap.items if i.spatial]
    assert spatial and all("Location:" in i.text for i in spatial)
    assert all(i.ssml.startswith("<speak") and "es-ES-ElviraNeural" in i.ssml for i in recap.items)


def test_deafblind_text_fits_braille_cells():
    match = generate_match(7)
    narrative = template_narrative(match, analyse(match))
    recap = adapt(match, narrative, Profile.DEAFBLIND)
    for item in recap.items:
        assert all(len(line) <= BRAILLE_CELLS for line in item.text.split("\n"))


def test_spatial_and_tone_helpers():
    match = generate_match(7)
    goal = next(e for e in match.events if e.type == EventType.GOAL)
    assert threat_tone_hz(goal) == 880
    assert describe_position(goal)
    kickoff = match.events[0]
    assert describe_position(kickoff) is None
