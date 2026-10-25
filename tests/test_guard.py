from fastapi.testclient import TestClient

from pitchside import api
from pitchside.guard import Guard, LRUCache, SlidingWindow


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_sliding_window_blocks_then_recovers():
    clock = FakeClock()
    window = SlidingWindow(limit=2, window=60, clock=clock)
    assert window.allow("a") and window.allow("a")
    assert not window.allow("a")
    assert window.retry_after("a") == 60
    clock.now = 59
    assert not window.allow("a")
    clock.now = 60
    assert window.allow("a")


def test_sliding_window_keys_are_independent():
    window = SlidingWindow(limit=1, window=60, clock=FakeClock())
    assert window.allow("a")
    assert window.allow("b")
    assert not window.allow("a")


def test_lru_cache_evicts_the_least_recently_used():
    cache = LRUCache(size=2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1  # "b" is now the oldest
    cache.put("c", 3)
    assert cache.get("b") is None
    assert cache.get("a") == 1 and cache.get("c") == 3
    assert len(cache) == 2


def test_guard_reads_environment_and_ignores_bad_values(monkeypatch):
    monkeypatch.setenv("PITCHSIDE_RATE_PER_MIN", "5")
    monkeypatch.setenv("PITCHSIDE_CLOUD_RUNS_PER_HOUR", "not-a-number")
    monkeypatch.setenv("PITCHSIDE_CACHE_SIZE", "-3")
    guard = Guard.from_env()
    assert guard.client_limit.limit == 5
    assert guard.cloud_budget.limit == 200
    assert guard.cache.size == 256


def test_repeat_requests_come_from_cache_and_new_ones_are_limited(monkeypatch):
    monkeypatch.setattr(api, "guard", Guard(per_client_per_minute=1))
    client = TestClient(api.app)
    params = {"seed": 11, "profiles": "deaf"}

    first = client.get("/api/recap", params=params)
    assert first.status_code == 200
    assert first.headers["X-Pitchside-Cache"] == "miss"

    again = client.get("/api/recap", params=params)  # cached: not counted against the limit
    assert again.status_code == 200
    assert again.headers["X-Pitchside-Cache"] == "hit"
    assert again.json() == first.json()

    other = client.get("/api/recap", params={"seed": 12, "profiles": "deaf"})
    assert other.status_code == 429
    assert int(other.headers["Retry-After"]) >= 1


def test_spent_cloud_budget_falls_back_to_offline_agents(monkeypatch):
    monkeypatch.setattr(api, "guard", Guard(cloud_runs_per_hour=1))
    monkeypatch.setattr(api, "_uses_cloud", lambda language: True)
    client = TestClient(api.app)

    first = client.get("/api/recap", params={"seed": 21, "profiles": "deaf"})
    assert first.status_code == 200
    assert "X-Pitchside-Mode" not in first.headers

    second = client.get("/api/recap", params={"seed": 22, "profiles": "deaf"})
    assert second.status_code == 200  # nobody is turned away
    assert second.headers["X-Pitchside-Mode"] == "offline-budget"
    assert second.json()["verification"]["passed"] is True
    assert second.json()["narrative"]["source"] == "template"


def test_warm_cache_makes_the_first_demo_request_a_cache_hit(monkeypatch):
    monkeypatch.setattr(api, "guard", Guard())
    api._warm_cache()
    assert len(api.guard.cache) == 8  # 4 matches x 2 depths
    client = TestClient(api.app)
    params = {"seed": 7, "language": "en", "depth": "analyst", "archetype": "red_card_swing"}
    first = client.get("/api/recap", params=params)
    assert first.status_code == 200 and first.headers["X-Pitchside-Cache"] == "hit"
