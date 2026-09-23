from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from app.config import Settings


class LLMProvider(Protocol):
    name: str
    is_demo: bool

    def complete(self, prompt: str) -> str: ...


@dataclass
class DeterministicProvider:
    name: str = "Deterministic demo mode"
    is_demo: bool = True

    def complete(self, prompt: str) -> str:
        raise RuntimeError("Deterministic demo mode does not call an LLM")


@dataclass
class OllamaProvider:
    base_url: str
    model: str
    timeout_seconds: int
    is_demo: bool = False

    @property
    def name(self) -> str:
        return f"Ollama ({self.model})"

    def complete(self, prompt: str) -> str:
        payload = json.dumps(
            {"model": self.model, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}
        ).encode()
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            body = json.loads(response.read())
        if not body.get("response"):
            raise RuntimeError("Ollama returned an empty response")
        return body["response"]


@dataclass
class BedrockProvider:
    region: str
    model_id: str
    is_demo: bool = False

    def __post_init__(self) -> None:
        import boto3

        self._client = boto3.client("bedrock-runtime", region_name=self.region)

    @property
    def name(self) -> str:
        return f"AWS Bedrock ({self.model_id})"

    def complete(self, prompt: str) -> str:
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2048,
                "temperature": 0.1,
                "messages": [{"role": "user", "content": prompt}],
            }
        )
        response = self._client.invoke_model(modelId=self.model_id, body=body)
        payload = json.loads(response["body"].read())
        return payload["content"][0]["text"]


@dataclass
class AnthropicProvider:
    model: str
    is_demo: bool = False

    def __post_init__(self) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    @property
    def name(self) -> str:
        return f"Anthropic ({self.model})"

    def complete(self, prompt: str) -> str:
        message = self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in message.content if getattr(block, "type", "") == "text")


def _ollama_available(settings: Settings) -> bool:
    try:
        request = urllib.request.Request(f"{settings.ollama_url}/api/tags", method="GET")
        with urllib.request.urlopen(request, timeout=0.75) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


def _aws_is_configured() -> bool:
    return bool(
        os.getenv("AWS_PROFILE")
        or os.getenv("AWS_ACCESS_KEY_ID")
        or os.getenv("AWS_WEB_IDENTITY_TOKEN_FILE")
        or os.getenv("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
    )


def build_provider(settings: Settings) -> LLMProvider:
    selected = settings.llm_provider
    if selected == "mock":
        return DeterministicProvider()
    if selected == "ollama":
        if not _ollama_available(settings):
            raise RuntimeError(f"Ollama is not reachable at {settings.ollama_url}")
        return OllamaProvider(settings.ollama_url, settings.ollama_model, settings.llm_timeout_seconds)
    if selected == "bedrock":
        if not _aws_is_configured():
            raise RuntimeError("AWS credentials are required when LLM_PROVIDER=bedrock")
        return BedrockProvider(settings.aws_region, settings.bedrock_model_id)
    if selected == "anthropic":
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        return AnthropicProvider(settings.anthropic_model)

    if _ollama_available(settings):
        return OllamaProvider(settings.ollama_url, settings.ollama_model, settings.llm_timeout_seconds)
    if _aws_is_configured():
        return BedrockProvider(settings.aws_region, settings.bedrock_model_id)
    if os.getenv("ANTHROPIC_API_KEY"):
        return AnthropicProvider(settings.anthropic_model)
    return DeterministicProvider()
