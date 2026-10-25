"""The simulated live replay: each frame knows only what had happened by its minute."""

import json
import re

from pitchside.agents.accessibility import BRAILLE_CELLS, Profile
from pitchside.agents.analyst import analyse
from pitchside.agents.narrator import Narrator, build_user_prompt
from pitchside.data.generator import ARCHETYPES, generate_match
from pitchside.models import Depth, EventType
from pitchside.orchestrator import Orchestrator
from pitchside.replay import build_replay, checkpoints

OFFLINE = Orchestrator(narrator=Narrator(None))
STORIES = (None, *ARCHETYPES)


def test_checkpoints_cover_every_goal_and_end_at_full_time():
    for archetype in STORIES:
        for seed in range(10):
            match = generate_match(seed, archetype=archetype)
            marks = checkpoints(match)
            assert marks == sorted(set(marks)) and marks[-1] == 90 and len(marks) <= 20
            for e in match.events:
                if e.type in (EventType.GOAL, EventType.RED_CARD) and 0 < e.minute < 90:
                    assert e.minute in marks


def test_every_frame_is_verified_and_knows_nothing_of_the_future():
    for archetype in STORIES:
        for depth in Depth:
            replay = build_replay(OFFLINE, seed=3, depth=depth, archetype=archetype)
            assert len(replay.frames) == len(replay.minutes)
            for minute, frame in zip(replay.minutes, replay.frames, strict=True):
                assert frame.verification.passed, (archetype, depth, minute)
                assert frame.match.clock == min(minute, 90)
                assert all(e.minute <= minute for e in frame.match.events)
                for s in frame.narrative.statements:
                    assert all(
                        frame.match.event_by_id(i) is not None for i in s.event_ids
                    ), (archetype, minute)
                    mentioned = [int(n) for n in re.findall(r"[Mm]inute (\d+)", s.text)]
                    assert all(n <= minute for n in mentioned), (minute, s.text)


def test_the_score_only_ever_grows_and_matches_the_goals_so_far():
    replay = build_replay(OFFLINE, seed=11, archetype="late_comeback")
    totals = []
    for minute, frame in zip(replay.minutes, replay.frames, strict=True):
        h, a = (int(x) for x in frame.analysis.final_score.split("-"))
        goals = [e for e in generate_match(11, archetype="late_comeback").events
                 if e.type == EventType.GOAL and e.minute <= minute]
        assert h + a == len(goals)
        totals.append(h + a)
    assert totals == sorted(totals)


def test_partial_frames_say_so_and_the_last_frame_is_the_full_recap():
    replay = build_replay(OFFLINE, seed=7)
    for minute, frame in zip(replay.minutes[:-1], replay.frames[:-1], strict=True):
        closing = frame.narrative.statements[-1]
        assert "score_so_far" in closing.claims and "final_score" not in closing.claims
        assert closing.text.startswith(f"After {minute} minutes")
        assert frame.story == []  # the storyline can only be judged once the match is over
    full = OFFLINE.run(seed=7)
    last = replay.frames[-1]
    assert last.narrative == full.narrative
    assert {k: r.model_dump() for k, r in last.recaps.items()} == {
        k: r.model_dump() for k, r in full.recaps.items()
    }


def test_the_story_is_judged_on_the_last_frame_only():
    replay = build_replay(OFFLINE, seed=3, archetype="red_card_swing", depth=Depth.ANALYST)
    assert all(f.story == [] for f in replay.frames[:-1])
    assert replay.frames[-1].story and replay.frames[-1].story[0].recovered


def test_braille_lines_stay_within_the_display_in_every_frame():
    replay = build_replay(OFFLINE, seed=3, archetype="red_card_swing",
                          profiles=[Profile.DEAFBLIND], depth=Depth.ANALYST)
    for frame in replay.frames:
        for item in frame.recaps["deafblind"].items:
            assert all(len(line) <= BRAILLE_CELLS for line in item.text.split("\n"))


def test_the_model_is_told_when_the_match_is_still_being_played():
    match = generate_match(7)
    part = match.until(35)
    partial = json.loads(build_user_prompt(part, analyse(part)))
    assert partial["score_so_far"] == analyse(part).final_score and partial["minutes_played"] == 35
    assert "final_score" not in partial
    full = json.loads(build_user_prompt(match, analyse(match)))
    assert "final_score" in full and "score_so_far" not in full
