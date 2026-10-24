"""Thin wrapper around a Microsoft Foundry / Azure OpenAI chat deployment.

Uses Azure's v1 API through the standard OpenAI client: no api-version needed. The
endpoint in .env can be given in any of these forms and is normalised:

    https://<resource>.services.ai.azure.com
    https://<resource>.openai.azure.com
    https://<resource>.services.ai.azure.com/openai/v1/responses   (a copied Target URI)

When no credentials are configured, `available` is False and the agents fall back to
deterministic templates, so the app always works offline.
"""

from __future__ import annotations

import json
import os

_CUT_MARKERS = ("/openai", "/api/projects", "/models")


def v1_base_url(endpoint: str) -> str:
    """Normalise any copied endpoint/Target URI to '<host>/openai/v1/'."""
    base = endpoint.strip()
    for marker in _CUT_MARKERS:
        base = base.split(marker)[0]
    return base.rstrip("/") + "/openai/v1/"


class LLMClient:
    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        deployment: str | None = None,
        api_version: str | None = None,  # kept for compatibility; the v1 API ignores it
    ) -> None:
        self.endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.deployment = deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT")
        self.api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION", "v1")

    @property
    def available(self) -> bool:
        return bool(self.endpoint and self.api_key and self.deployment)

    @property
    def base_url(self) -> str:
        return v1_base_url(self.endpoint or "")

    def complete_json(self, system: str, user: str) -> dict:
        from openai import OpenAI  # imported lazily so offline mode needs no setup

        client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return json.loads(response.choices[0].message.content)
