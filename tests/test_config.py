from app.config import Settings
from app.providers import DeterministicProvider, build_provider


def test_default_provider_stays_free_even_when_cloud_credentials_exist(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "configured-but-never-used")
    settings = Settings.from_env()
    provider = build_provider(settings)
    assert settings.llm_provider == "mock"
    assert isinstance(provider, DeterministicProvider)
