import importlib.util

from fastapi.testclient import TestClient

from pitchside.api import app

client = TestClient(app)


def test_api_health_and_recap():
    assert client.get("/health").json()["status"] == "ok"
    r = client.get("/api/recap", params={"seed": 7, "profiles": "deaf,blind"})
    assert r.status_code == 200
    body = r.json()
    assert set(body["recaps"]) == {"deaf", "blind"}
    assert body["verification"]["passed"] is True
    assert body["engine"] == "plain"


def test_api_validates_input():
    assert client.get("/api/recap", params={"profiles": "martian"}).status_code == 422
    assert client.get("/api/recap", params={"language": "xx"}).status_code == 422
    assert client.get("/api/recap", params={"seed": -1}).status_code == 422


def test_ui_is_served():
    r = client.get("/")
    assert r.status_code == 200 and "Pitchside" in r.text


def test_engine_is_validated():
    assert client.get("/api/recap", params={"engine": "quantum"}).status_code == 422


def test_agent_framework_engine_is_opt_in():
    r = client.get("/api/recap", params={"engine": "agent_framework", "profiles": "deaf"})
    installed = importlib.util.find_spec("agent_framework") is not None
    assert r.status_code == (200 if installed else 501)
    if installed:
        assert r.json()["verification"]["passed"] is True
        assert r.json()["engine"] == "agent_framework"


def test_depth_and_archetype_are_validated():
    assert client.get("/api/recap", params={"depth": "expert"}).status_code == 422
    assert client.get("/api/recap", params={"archetype": "nonsense"}).status_code == 422


def test_story_matches_report_whether_the_analyst_found_the_storyline():
    r = client.get(
        "/api/recap",
        params={"seed": 3, "profiles": "deaf", "archetype": "red_card_swing", "depth": "analyst"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["depth"] == "analyst"
    assert body["verification"]["passed"] is True
    assert body["story"] and body["story"][0]["recovered"] is True


def test_replay_returns_verified_frames_ending_at_full_time():
    r = client.get("/api/replay", params={"seed": 3, "profiles": "deaf", "archetype": "red_card_swing"})
    assert r.status_code == 200
    body = r.json()
    assert body["minutes"][-1] == 90 and len(body["frames"]) == len(body["minutes"])
    assert all(f["verification"]["passed"] for f in body["frames"])
    assert body["frames"][0]["match"]["clock"] == body["minutes"][0]
    assert client.get("/api/replay", params={"seed": 3, "profiles": "deaf",
                                             "archetype": "red_card_swing"}).headers["X-Pitchside-Cache"] == "hit"


def test_replay_validates_input():
    assert client.get("/api/replay", params={"depth": "expert"}).status_code == 422
    assert client.get("/api/replay", params={"archetype": "nonsense"}).status_code == 422
    assert client.get("/api/replay", params={"profiles": "martian"}).status_code == 422


def test_fault_demo_is_validated_and_labelled():
    assert client.get("/api/recap", params={"fault": "gremlins"}).status_code == 422
    r = client.get("/api/recap", params={"seed": 3, "profiles": "deaf", "archetype": "red_card_swing",
                                         "fault": "wrong_score"})
    assert r.status_code == 200
    trace = r.json()["trace"]
    assert any(t["agent"] == "demo" and t["detail"].startswith("INJECTED FAULT") for t in trace)
    assert any(t["status"] == "rejected" for t in trace)
    assert r.json()["verification"]["passed"] is True
