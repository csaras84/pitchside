"""The Analyst's "why it matters" reasons, checked on hand-built matches."""

from pitchside.agents.analyst import MAX_INSIGHTS, SCORE_STATE_CODES, analyse, insights_for
from pitchside.data.generator import generate_match
from pitchside.models import Event, EventType, Match

HOME, AWAY = "Northgate FC", "Harbour United"
GOAL, SHOT, SAVE, CARD = (
    EventType.GOAL, EventType.SHOT, EventType.SAVE, EventType.YELLOW_CARD,
)


def build(*spec: tuple[int, EventType, str, float]) -> Match:
    """A match from (minute, type, team, xg) rows; ids follow the order given."""
    rows = [(0, EventType.KICKOFF, HOME, 0.0), *spec, (90, EventType.FULL_TIME, HOME, 0.0)]
    events = [
        Event(id=i, minute=m, type=t, team=team, player=f"Player {i}", x=80, y=50, xg=xg)
        for i, (m, t, team, xg) in enumerate(rows)
    ]
    return Match(home=HOME, away=AWAY, seed=0, events=events)


def codes(match: Match, event_id: int) -> list[str]:
    return [i.code for i in insights_for(match, match.event_by_id(event_id))]


def test_score_state_reasons_follow_the_scoreline():
    match = build(
        (10, GOAL, HOME, 0.3),  # 1-0  opens the scoring
        (20, GOAL, AWAY, 0.3),  # 1-1  equalises
        (30, GOAL, HOME, 0.3),  # 2-1  takes the lead
        (40, GOAL, HOME, 0.3),  # 3-1  extends the lead
        (50, GOAL, AWAY, 0.3),  # 3-2  pulls one back
    )
    first = [codes(match, i)[0] for i in range(1, 6)]
    assert first == ["opens_scoring", "equalises", "takes_lead", "extends_lead", "cuts_deficit"]
    assert set(first) == set(SCORE_STATE_CODES)
    evidence = [insights_for(match, match.event_by_id(i))[0].evidence for i in range(1, 6)]
    assert [e["score_after"] for e in evidence] == ["1-0", "1-1", "2-1", "3-1", "3-2"]


def test_late_goal_is_flagged_only_when_it_changes_the_game():
    late_opener = build((85, GOAL, HOME, 0.3))
    assert "late_goal" in codes(late_opener, 1)
    late_extra = build((10, GOAL, HOME, 0.3), (20, GOAL, HOME, 0.3), (85, GOAL, HOME, 0.3))
    assert "late_goal" not in codes(late_extra, 3)  # 3-0 is already decided


def test_against_the_run_needs_evidence_in_the_previous_minutes():
    pressure = [(m, SHOT, AWAY, 0.1) for m in (40, 41, 42, 43)]  # 4 shots = 12.0 threat
    match = build(*pressure, (50, GOAL, HOME, 0.3))
    found = {i.code: i for i in insights_for(match, match.event_by_id(5))}
    assert "against_the_run" in found
    assert found["against_the_run"].evidence == {"threat_other": 12.0, "threat_team": 0.0}
    assert "12.0 to 0.0" in found["against_the_run"].text

    quiet = build((50, GOAL, HOME, 0.3))
    assert "against_the_run" not in codes(quiet, 1)


def test_no_history_means_no_claim_about_the_run_of_play():
    early = build((2, SHOT, AWAY, 0.1), (3, SHOT, AWAY, 0.1), (4, SHOT, AWAY, 0.1),
                  (5, GOAL, HOME, 0.3))
    assert "against_the_run" not in codes(early, 4)  # only 4 minutes of history: too few
    enough = build((2, SHOT, AWAY, 0.1), (3, SHOT, AWAY, 0.1), (4, SHOT, AWAY, 0.1),
                   (6, GOAL, HOME, 0.3))
    assert "against_the_run" in codes(enough, 4)  # 5 minutes of history is enough


def test_momentum_shift_after_a_goal():
    before = [(m, SHOT, AWAY, 0.1) for m in (20, 21, 22)]  # away 9.0
    after = [(m, SHOT, HOME, 0.1) for m in (35, 36, 37)]  # home 9.0
    match = build(*before, (30, GOAL, HOME, 0.3), *after)
    found = {i.code: i for i in insights_for(match, match.event_by_id(4))}
    shift = found["momentum_shift"]
    assert shift.evidence == {
        "threat_after_team": 9.0, "threat_after_other": 0.0,
        "threat_before_team": 0.0, "threat_before_other": 9.0,
    }


def test_chance_reasons_depend_on_the_score_at_the_time():
    level = build((65, SHOT, HOME, 0.3))
    assert codes(level, 1)[0] == "would_have_led"
    early = build((5, SHOT, HOME, 0.3))
    assert codes(early, 1) == []  # a goal in minute 5 "would give the lead" is true of any chance
    trailing = build((10, GOAL, AWAY, 0.3), (30, SAVE, HOME, 0.4))
    assert codes(trailing, 2)[0] == "would_have_levelled"
    assert codes(trailing, 2)[-1] == "chance_quality"
    leading = build((10, GOAL, HOME, 0.3), (30, SAVE, HOME, 0.4))
    assert "would_have_led" not in codes(leading, 2)


def test_small_chances_get_no_explanation():
    assert codes(build((30, SHOT, HOME, 0.1)), 1) == []  # below the big-chance threshold


def test_only_the_first_booking_is_called_first():
    match = build((20, CARD, HOME, 0.0), (30, CARD, AWAY, 0.0))
    assert "first_booking" in codes(match, 1)
    assert "first_booking" not in codes(match, 2)


def test_reasons_are_capped_and_agree_with_the_data_on_generated_matches():
    for seed in range(40):
        match = generate_match(seed)
        for moment in analyse(match).key_moments:
            assert len(moment.insights) <= MAX_INSIGHTS
            if moment.kind == "goal":
                first = moment.insights[0]
                assert first.code in SCORE_STATE_CODES
                assert first.evidence["score_after"] == moment.facts["score"]
            for insight in moment.insights:
                assert insight.text and insight.code


def test_until_hides_the_future():
    full = generate_match(7)
    part = full.until(30)
    assert part.clock == 30 and not part.is_final and full.is_final
    assert all(e.minute <= 30 for e in part.events)
    assert not any(e.type == EventType.FULL_TIME for e in part.events)
    goals = [e for e in full.events if e.type == GOAL and e.minute <= 30]
    assert sum(part.score_after()) == len(goals)
    assert analyse(part).clock == 30
