from __future__ import annotations

import os
from dataclasses import dataclass


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    ollama_url: str
    ollama_model: str
    bedrock_model_id: str
    aws_region: str
    anthropic_model: str
    llm_timeout_seconds: int
    max_upload_bytes: int
    cors_origins: tuple[str, ...]

    @classmethod
    def from_env(cls) -> Settings:
        provider = os.getenv("LLM_PROVIDER", "mock").strip().lower()
        allowed = {"auto", "mock", "ollama", "bedrock", "anthropic"}
        if provider not in allowed:
            raise ValueError(f"LLM_PROVIDER must be one of: {', '.join(sorted(allowed))}")

        origins = tuple(
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if origin.strip()
        )
        return cls(
            llm_provider=provider,
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            bedrock_model_id=os.getenv(
                "BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"
            ),
            aws_region=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
            llm_timeout_seconds=_positive_int("LLM_TIMEOUT_SECONDS", 60),
            max_upload_bytes=_positive_int("MAX_UPLOAD_MB", 10) * 1024 * 1024,
            cors_origins=origins,
        )
