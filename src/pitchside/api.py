"""FastAPI app. Run with:  uvicorn pitchside.api:app --reload"""

from __future__ import annotations

import importlib.util
import logging
import os
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from .agents.accessibility import SUPPORTED_LANGUAGES, Profile
from .agents.narrator import Narrator
from .agents.translator import Translator
from .data.generator import ARCHETYPES
from .faults import FAULTS
from .guard import Guard
from .llm import LLMClient
from .models import Depth
from .orchestrator import Orchestrator, PipelineResult
from .replay import Replay, build_replay

log = logging.getLogger("pitchside")
orchestrator = Orchestrator(narrator=Narrator(LLMClient()), translator=Translator())
guard = Guard.from_env()
ENGINES = ("plain", "agent_framework")
_engines: dict[str, Any] = {}


def _cache_key(
    seed: int,
    profiles: list[Profile],
    language: str,
    engine: str,
    depth: str,
    archetype: str,
    fault: str = "",
) -> tuple:
    names = tuple(sorted({p.value for p in profiles}))
    return (seed, names, language, engine, depth, archetype, fault)


def _warm_cache() -> None:
    """Pre-compute the demo recaps (the page's default request for each story, at both depths)
    so a visitor's first click is answered from memory instead of waiting for the model.
    Best effort: it stops quietly if the cloud budget runs out or anything fails."""
    profiles = list(Profile)
    for archetype in ("", *ARCHETYPES):
        for depth in Depth:
            key = _cache_key(7, profiles, "en", "plain", depth.value, archetype)
            if guard.cache.get(key) is not None:
                continue
            if _uses_cloud("en") and not guard.cloud_budget.allow("all"):
                return
            try:
                result = orchestrator.run(
                    seed=7, profiles=profiles, language="en", depth=depth,
                    archetype=archetype or None,
                )
            except Exception:  # warming must never stop the app starting
                log.warning("cache warm-up skipped %s/%s", archetype or "ordinary", depth.value, exc_info=True)
                continue
            guard.cache.put(key, result)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if os.getenv("PITCHSIDE_WARM_CACHE") == "1":
        threading.Thread(target=_warm_cache, daemon=True).start()
    yield


app = FastAPI(title="Pitchside", version="0.1.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)


def _offline_orchestrator() -> Orchestrator:
    """Template agents only: no LLM and no Translator. Used once the cloud budget is spent."""
    translator = Translator()
    translator.key = None
    return Orchestrator(narrator=Narrator(None), translator=translator)


def _agent_framework_engine() -> Any:
    """Built on first use, so the app runs fine without the optional package installed."""
    if "agent_framework" not in _engines:
        from .af_workflow import AgentFrameworkOrchestrator, AgentNarrator

        _engines["agent_framework"] = AgentFrameworkOrchestrator(
            narrator=AgentNarrator(LLMClient()), translator=Translator()
        )
    return _engines["agent_framework"]


def _uses_cloud(language: str) -> bool:
    """True when this request would spend Foundry tokens or Translator characters."""
    llm = orchestrator.narrator.llm
    return bool(llm and llm.available) or (language != "en" and orchestrator.translator.available)


def _client_id(request: Request) -> str:
    """Best-effort client address. Behind the hosting proxy the last X-Forwarded-For entry is
    the one the proxy itself saw. It is a soft limit; the global cloud budget is the real cap."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _validated(profiles: str, depth: str, archetype: str) -> list[Profile]:
    if depth not in {d.value for d in Depth}:
        raise HTTPException(422, f"depth must be one of {[d.value for d in Depth]}")
    if archetype and archetype not in ARCHETYPES:
        raise HTTPException(422, f"archetype must be empty or one of {list(ARCHETYPES)}")
    try:
        chosen = [Profile(p.strip()) for p in profiles.split(",") if p.strip()]
    except ValueError as exc:
        raise HTTPException(422, f"unknown profile: {exc}") from exc
    if not chosen:
        raise HTTPException(422, "at least one profile is required")
    return chosen


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_configured": bool(orchestrator.narrator.llm and orchestrator.narrator.llm.available),
        "translator_configured": orchestrator.translator.available,
        "languages": list(SUPPORTED_LANGUAGES),
        "agent_framework_installed": importlib.util.find_spec("agent_framework") is not None,
    }


@app.get("/api/recap", response_model=PipelineResult)
def recap(
    request: Request,
    response: Response,
    seed: int = Query(7, ge=0, le=1_000_000),
    profiles: str = Query(",".join(p.value for p in Profile)),
    language: str = Query("en"),
    engine: str = Query("plain"),
    depth: str = Query("casual"),
    archetype: str = Query(""),
    fault: str = Query(""),
) -> PipelineResult:
    if engine not in ENGINES:
        raise HTTPException(422, f"engine must be one of {list(ENGINES)}")
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(422, f"language must be one of {list(SUPPORTED_LANGUAGES)}")
    if fault and fault not in FAULTS:
        raise HTTPException(422, f"fault must be empty or one of {list(FAULTS)}")
    chosen = _validated(profiles, depth, archetype)

    # A repeat of an earlier request is answered from memory: no limit applies, no cost.
    key = _cache_key(seed, chosen, language, engine, depth, archetype, fault)
    cached = guard.cache.get(key)
    if cached is not None:
        response.headers["X-Pitchside-Cache"] = "hit"
        return cached

    client = _client_id(request)
    if not guard.client_limit.allow(client):
        raise HTTPException(
            429,
            "Too many requests. Please wait a moment and try again.",
            headers={"Retry-After": str(guard.client_limit.retry_after(client))},
        )

    runner: Any = orchestrator
    if engine == "agent_framework":
        try:
            runner = _agent_framework_engine()
        except ImportError as exc:
            raise HTTPException(
                501, "Agent Framework is not installed. Run: pip install agent-framework"
            ) from exc

    if _uses_cloud(language) and not guard.cloud_budget.allow("all"):
        # Budget spent: answer with the offline agents rather than refuse anyone.
        response.headers["X-Pitchside-Mode"] = "offline-budget"
        return _offline_orchestrator().run(
            seed=seed, profiles=chosen, language=language, depth=Depth(depth),
            archetype=archetype or None, fault=fault or None,
        )

    result = runner.run(
        seed=seed, profiles=chosen, language=language, depth=Depth(depth),
        archetype=archetype or None, fault=fault or None,
    )
    guard.cache.put(key, result)
    response.headers["X-Pitchside-Cache"] = "miss"
    return result


@app.get("/api/replay", response_model=Replay)
def replay(
    request: Request,
    response: Response,
    seed: int = Query(7, ge=0, le=1_000_000),
    profiles: str = Query(",".join(p.value for p in Profile)),
    depth: str = Query("casual"),
    archetype: str = Query(""),
) -> Replay:
    """The match as it unfolds: one verified recap per checkpoint minute, using only the events
    up to that minute. Written by the built-in agents (no model tokens), so it costs nothing
    to play and never touches the cloud budget; it is English only."""
    chosen = _validated(profiles, depth, archetype)
    key = ("replay", *_cache_key(seed, chosen, "en", "plain", depth, archetype))
    cached = guard.cache.get(key)
    if cached is not None:
        response.headers["X-Pitchside-Cache"] = "hit"
        return cached
    client = _client_id(request)
    if not guard.client_limit.allow(client):
        raise HTTPException(
            429,
            "Too many requests. Please wait a moment and try again.",
            headers={"Retry-After": str(guard.client_limit.retry_after(client))},
        )
    result = build_replay(
        _offline_orchestrator(), seed=seed, profiles=chosen, depth=Depth(depth),
        archetype=archetype or None,
    )
    guard.cache.put(key, result)
    response.headers["X-Pitchside-Cache"] = "miss"
    return result


app.mount(
    "/",
    StaticFiles(directory=Path(__file__).parent / "static", html=True),
    name="static",
)
