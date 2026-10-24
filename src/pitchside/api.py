"""FastAPI app. Run with:  uvicorn pitchside.api:app --reload"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from .agents.accessibility import SUPPORTED_LANGUAGES, Profile
from .agents.narrator import Narrator
from .agents.translator import Translator
from .llm import LLMClient
from .orchestrator import Orchestrator, PipelineResult

app = FastAPI(title="Pitchside", version="0.1.0")
orchestrator = Orchestrator(narrator=Narrator(LLMClient()), translator=Translator())
ENGINES = ("plain", "agent_framework")
_engines: dict[str, Any] = {}


def _agent_framework_engine() -> Any:
    """Built on first use, so the app runs fine without the optional package installed."""
    if "agent_framework" not in _engines:
        from .af_workflow import AgentFrameworkOrchestrator, AgentNarrator

        _engines["agent_framework"] = AgentFrameworkOrchestrator(
            narrator=AgentNarrator(LLMClient()), translator=Translator()
        )
    return _engines["agent_framework"]


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
    seed: int = Query(7, ge=0, le=1_000_000),
    profiles: str = Query(",".join(p.value for p in Profile)),
    language: str = Query("en"),
    engine: str = Query("plain"),
) -> PipelineResult:
    if engine not in ENGINES:
        raise HTTPException(422, f"engine must be one of {list(ENGINES)}")
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(422, f"language must be one of {list(SUPPORTED_LANGUAGES)}")
    try:
        chosen = [Profile(p.strip()) for p in profiles.split(",") if p.strip()]
    except ValueError as exc:
        raise HTTPException(422, f"unknown profile: {exc}") from exc
    if not chosen:
        raise HTTPException(422, "at least one profile is required")
    if engine == "agent_framework":
        try:
            runner = _agent_framework_engine()
        except ImportError as exc:
            raise HTTPException(
                501, "Agent Framework is not installed. Run: pip install agent-framework"
            ) from exc
        return runner.run(seed=seed, profiles=chosen, language=language)
    return orchestrator.run(seed=seed, profiles=chosen, language=language)


app.mount(
    "/",
    StaticFiles(directory=Path(__file__).parent / "static", html=True),
    name="static",
)
