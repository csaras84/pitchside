"""Thin wrapper around an Azure OpenAI-compatible chat deployment (e.g. one hosted in
Microsoft Foundry). When no credentials are configured, `available` is False and the
agents fall back to deterministic templates, so the app always works offline."""

from __future__ import annotations

import json
import os


class LLMClient:
    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        deployment: str | None = None,
        api_version: str | None = None,
    ) -> None:
        self.endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.deployment = deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT")
        self.api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")

    @property
    def available(self) -> bool:
        return bool(self.endpoint and self.api_key and self.deployment)

    def complete_json(self, system: str, user: str) -> dict:
        from openai import AzureOpenAI  # imported lazily so offline mode needs no setup

        client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version,
        )
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
