"""Check the Azure AI Translator connection, one short request per language.

    .venv\\Scripts\\python scripts\\check_translator.py

Reads .env, never prints the key, and shows the real HTTP status so a wrong key or region is
easy to tell apart (the app itself quietly falls back to English on any error).
"""

import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
for raw in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")

KEY = os.getenv("AZURE_TRANSLATOR_KEY", "")
REGION = os.getenv("AZURE_TRANSLATOR_REGION", "")
ENDPOINT = (os.getenv("AZURE_TRANSLATOR_ENDPOINT") or "https://api.cognitive.microsofttranslator.com").rstrip("/")
SAMPLE = "Goal! In minute 69, Liam Hartley scores for Northgate FC. It's 1-0."


def main() -> int:
    print(f"key set: {bool(KEY)} (length {len(KEY)}), region: {REGION!r}, endpoint: {ENDPOINT}")
    if not KEY or not REGION:
        print("FAILED: AZURE_TRANSLATOR_KEY and AZURE_TRANSLATOR_REGION must both be set in .env")
        return 1
    if REGION != REGION.strip().lower().replace(" ", ""):
        print("note: the region should be lowercase with no spaces, for example 'centralindia'")
    failures = 0
    for lang in ("es", "fr", "hi", "ta"):
        try:
            r = httpx.post(
                f"{ENDPOINT}/translate",
                params={"api-version": "3.0", "from": "en", "to": lang},
                headers={
                    "Ocp-Apim-Subscription-Key": KEY,
                    "Ocp-Apim-Subscription-Region": REGION,
                    "Content-Type": "application/json",
                },
                json=[{"Text": SAMPLE}],
                timeout=15,
            )
        except httpx.HTTPError as exc:
            print(f"  {lang}: network error: {exc}")
            failures += 1
            continue
        if r.status_code == 200:
            print(f"  {lang}: OK  {r.json()[0]['translations'][0]['text']}")
        else:
            failures += 1
            print(f"  {lang}: HTTP {r.status_code}  {r.text[:200]}")
    print("SUCCESS" if not failures else f"FAILED ({failures} of 4)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
