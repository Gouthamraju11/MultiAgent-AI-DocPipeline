from __future__ import annotations

import os


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is missing")
    return value


MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


def table_name() -> str:
    return required_env("TABLE_NAME")


def document_bucket() -> str:
    return required_env("DOCUMENT_BUCKET")


def bedrock_model_id() -> str:
    return os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
