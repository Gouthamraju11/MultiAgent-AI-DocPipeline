import os

import pytest
from fastapi.testclient import TestClient

os.environ["LLM_PROVIDER"] = "mock"

from app.api import create_app  # noqa: E402
from app.config import Settings  # noqa: E402


@pytest.fixture
def settings() -> Settings:
    return Settings(
        llm_provider="mock",
        ollama_url="http://localhost:11434",
        ollama_model="llama3.2",
        bedrock_model_id="unused",
        aws_region="us-east-1",
        anthropic_model="unused",
        llm_timeout_seconds=5,
        max_upload_bytes=1024,
        cors_origins=("http://localhost:5173",),
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
