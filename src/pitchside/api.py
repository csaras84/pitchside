"""FastAPI app. Run with:  uvicorn pitchside.api:app --reload"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from .agents.accessibility import SUPPORTED_LANGUAGES, Profile
from .agents.narrator import Narrator
from .agents.translator import Translator
from .llm import LLMClient
from .orchestrator import Orchestrator, PipelineResult

app = FastAPI(title="Pitchside", version="0.1.0")
orchestrator = Orchestrator(narrator=Narrator(LLMClient()), translator=Translator())


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_configured": bool(orchestrator.narrator.llm and orchestrator.narrator.llm.available),
        "translator_configured": orchestrator.translator.available,
        "languages": list(SUPPORTED_LANGUAGES),
    }


@app.get("/api/recap", response_model=PipelineResult)
def recap(
    seed: int = Query(7, ge=0, le=1_000_000),
    profiles: str = Query(",".join(p.value for p in Profile)),
    language: str = Query("en"),
) -> PipelineResult:
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(422, f"language must be one of {list(SUPPORTED_LANGUAGES)}")
    try:
        chosen = [Profile(p.strip()) for p in profiles.split(",") if p.strip()]
    except ValueError as exc:
        raise HTTPException(422, f"unknown profile: {exc}") from exc
    if not chosen:
        raise HTTPException(422, "at least one profile is required")
    return orchestrator.run(seed=seed, profiles=chosen, language=language)


app.mount(
    "/",
    StaticFiles(directory=Path(__file__).parent / "static", html=True),
    name="static",
)
