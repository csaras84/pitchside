"""Cost and abuse guardrails for a publicly hosted demo.

Judges must be able to use the app freely (no sign-in), but anyone on the internet can
reach a public URL, and every uncached run can spend Foundry tokens and Translator
characters. Three small, in-memory protections keep the bill bounded:

* a result cache: the same request is answered from memory and costs nothing
* a per-client limit on uncached runs (a soft limit: a client address can be spoofed)
* a global hourly budget for runs that call cloud services (the real cap). When it is
  spent, the app does not refuse anyone: it answers with the offline template agents.

State lives in one process. That is deliberate for a demo, and it means every replica
of a scaled-out app has its own counters, so keep the replica count small.
"""

from __future__ import annotations

import math
import os
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable, Hashable
from typing import Any


class SlidingWindow:
    """Allow at most `limit` events per `window` seconds for each key."""

    def __init__(
        self,
        limit: int,
        window: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window = window
        self._clock = clock
        self._hits: dict[Hashable, deque[float]] = {}
        self._lock = threading.Lock()

    def _trim(self, hits: deque[float], now: float) -> None:
        while hits and now - hits[0] >= self.window:
            hits.popleft()

    def allow(self, key: Hashable) -> bool:
        """Record one event for `key` and return True, or return False if over the limit."""
        now = self._clock()
        with self._lock:
            if len(self._hits) > 10_000:  # stop unbounded growth from many distinct keys
                for key_, h in list(self._hits.items()):
                    self._trim(h, now)
                    if not h:
                        del self._hits[key_]
            hits = self._hits.setdefault(key, deque())
            self._trim(hits, now)
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def retry_after(self, key: Hashable) -> int:
        """Whole seconds until `key` may try again (at least 1)."""
        now = self._clock()
        with self._lock:
            hits = self._hits.get(key)
            if not hits:
                return 1
            self._trim(hits, now)
            if not hits:
                return 1
            return max(1, math.ceil(hits[0] + self.window - now))


class LRUCache:
    """A small least-recently-used cache."""

    def __init__(self, size: int) -> None:
        self.size = size
        self._items: OrderedDict[Hashable, Any] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> Any | None:
        with self._lock:
            if key not in self._items:
                return None
            self._items.move_to_end(key)
            return self._items[key]

    def put(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.size:
                self._items.popitem(last=False)

    def __len__(self) -> int:
        return len(self._items)


def _int_env(name: str, default: int) -> int:
    """Read a positive integer from the environment; ignore anything else."""
    try:
        value = int(os.getenv(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


class Guard:
    def __init__(
        self,
        per_client_per_minute: int = 30,
        cloud_runs_per_hour: int = 200,
        cache_size: int = 256,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client_limit = SlidingWindow(per_client_per_minute, 60, clock)
        self.cloud_budget = SlidingWindow(cloud_runs_per_hour, 3600, clock)
        self.cache = LRUCache(cache_size)

    @classmethod
    def from_env(cls) -> Guard:
        return cls(
            per_client_per_minute=_int_env("PITCHSIDE_RATE_PER_MIN", 30),
            cloud_runs_per_hour=_int_env("PITCHSIDE_CLOUD_RUNS_PER_HOUR", 200),
            cache_size=_int_env("PITCHSIDE_CACHE_SIZE", 256),
        )
