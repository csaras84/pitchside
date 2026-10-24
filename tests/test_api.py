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
