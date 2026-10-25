"""Run the whole pipeline as a Microsoft Agent Framework workflow with the real model.

    pip install agent-framework          (once, inside the project's virtual environment)
    .venv\\Scripts\\python scripts\\try_agent_framework.py [seed] [casual|analyst]

Shows each step the workflow executed, who wrote the recap, and the final text.
"""

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

from pitchside.af_workflow import AgentFrameworkOrchestrator, AgentNarrator
from pitchside.llm import LLMClient
from pitchside.models import Depth


def main() -> int:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    depth = Depth(sys.argv[2]) if len(sys.argv) > 2 else Depth.CASUAL
    llm = LLMClient()
    print(f"Foundry configured: {llm.available}  (if False, the narrator uses the template)\n")
    result = AgentFrameworkOrchestrator(narrator=AgentNarrator(llm)).run(seed=seed, depth=depth)

    print(f"Match seed {seed}: final score {result.analysis.final_score}")
    print(f"Narrator source: {result.narrative.source.upper()}\n")
    print("Workflow trace:")
    for t in result.trace:
        extra = f"  -> {t.detail}" if t.detail else ""
        print(f"  {t.agent:<14} {t.action:<24} {t.status:<9} {t.ms:>8.0f} ms{extra}")
    v = result.verification
    print(f"\nFinal verification: passed={v.passed}, checked={v.checked} statements\n")
    for s in result.narrative.statements:
        print(f"  - {s.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
