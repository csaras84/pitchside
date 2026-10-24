"""Check the Foundry / Azure OpenAI connection before running the whole app.

Run from the project folder:
    .venv\\Scripts\\python scripts\\check_foundry.py

It reads .env (simple KEY=VALUE lines), never prints secret values, and makes one tiny
JSON request to your deployment.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def load_env(path: Path) -> None:
    if not path.exists():
        print(f"No .env found at {path}. Copy .env.example to .env and fill it in.")
        sys.exit(1)
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def main() -> int:
    load_env(ROOT / ".env")
    from pitchside.llm import LLMClient

    llm = LLMClient()
    for name in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT"):
        print(f"{name}: {'set' if os.getenv(name) else 'MISSING'}")
    if not llm.available:
        print("\nFill in the missing values in .env and run again.")
        return 1

    print(f"\nCalling:    {llm.base_url}chat/completions")
    print(f"Deployment: {llm.deployment}")
    try:
        reply = llm.complete_json(
            'Reply with JSON only: {"ok": true, "word": "<one short football word>"}',
            "Say hello.",
        )
    except Exception as exc:  # noqa: BLE001  show the real error to the person debugging
        print(f"\nFAILED: {type(exc).__name__}: {str(exc)[:300]}")
        print("\nIf this is a 404: the deployment NAME must match the portal exactly")
        print("(case-sensitive) and live in the same resource as the host above.")
        print("If it is a 401: the key does not belong to this resource.")
        print("If it mentions 'temperature' or 'response_format': tell Claude.")
        return 1
    print(f"\nSUCCESS. Model replied: {reply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
