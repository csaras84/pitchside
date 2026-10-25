"""Run the whole pipeline with the real Foundry model and show what happened.

    .venv\\Scripts\\python scripts\\try_llm.py [seed] [casual|analyst]

Shows who wrote the recap (llm or template), every Verifier decision, and the final text.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

for raw in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")

from pitchside.agents.narrator import Narrator
from pitchside.llm import LLMClient
from pitchside.models import Depth
from pitchside.orchestrator import Orchestrator


def main() -> int:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    depth = Depth(sys.argv[2]) if len(sys.argv) > 2 else Depth.CASUAL
    llm = LLMClient()
    if not llm.available:
        print("Foundry is not configured in .env")
        return 1
    result = Orchestrator(narrator=Narrator(llm)).run(seed=seed, profiles=[], depth=depth)

    print(f"Match seed {seed} ({depth.value} depth): final score {result.analysis.final_score}")
    print(f"Narrator source: {result.narrative.source.upper()}\n")
    print("Agent trace:")
    for t in result.trace:
        if t.agent in ("narrator", "verifier"):
            extra = f"  -> {t.detail}" if t.detail else ""
            print(f"  {t.agent:<9} {t.action:<22} {t.status:<9} {t.ms:>8.0f} ms{extra}")
    v = result.verification
    print(f"\nFinal verification: passed={v.passed}, checked={v.checked} statements")
    print("\nRecap:")
    for s in result.narrative.statements:
        print(f"  - {s.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
