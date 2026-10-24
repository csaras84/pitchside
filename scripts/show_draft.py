"""Show the model's raw first draft next to what the Verifier says about it.

    .venv\\Scripts\\python scripts\\show_draft.py [seed]
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

from pitchside.agents.analyst import analyse
from pitchside.agents.narrator import Narrator
from pitchside.agents.verifier import verify
from pitchside.data.generator import generate_match
from pitchside.llm import LLMClient


def main() -> int:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    match = generate_match(seed)
    analysis = analyse(match)
    draft = Narrator(LLMClient()).narrate(match, analysis)
    result = verify(match, draft)
    print(f"Verifier: passed={result.passed}\n")
    for i, s in enumerate(draft.statements):
        print(f"[{i}] {s.text}")
        print(f"     event_ids={s.event_ids} claims={s.claims}")
        for issue in result.issues:
            if issue.statement_index == i:
                print(f"     ISSUE: {issue.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
