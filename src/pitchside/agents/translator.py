"""Translator agent: multilingual output via Azure AI Translator.

Degrades gracefully: with no credentials, or on any service error, the original English
text is returned and `translated` is False so the UI can say so honestly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx


@dataclass
class TranslationResult:
    texts: list[str]
    translated: bool


class Translator:
    def __init__(
        self,
        key: str | None = None,
        region: str | None = None,
        endpoint: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.key = key or os.getenv("AZURE_TRANSLATOR_KEY")
        self.region = region or os.getenv("AZURE_TRANSLATOR_REGION")
        self.endpoint = (
            endpoint
            or os.getenv("AZURE_TRANSLATOR_ENDPOINT")
            or "https://api.cognitive.microsofttranslator.com"
        ).rstrip("/")
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.key and self.region)

    def translate(self, texts: list[str], to: str) -> TranslationResult:
        if to == "en" or not texts or not self.available:
            return TranslationResult(list(texts), False)
        try:
            resp = httpx.post(
                f"{self.endpoint}/translate",
                params={"api-version": "3.0", "from": "en", "to": to},
                headers={
                    "Ocp-Apim-Subscription-Key": self.key,
                    "Ocp-Apim-Subscription-Region": self.region,
                    "Content-Type": "application/json",
                },
                json=[{"Text": t} for t in texts],
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return TranslationResult([d["translations"][0]["text"] for d in data], True)
        except (httpx.HTTPError, KeyError, IndexError, ValueError):
            return TranslationResult(list(texts), False)
