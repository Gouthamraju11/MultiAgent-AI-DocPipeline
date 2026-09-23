"""ASGI entry point kept for `uvicorn main:app` compatibility."""

from app.api import app, create_app

__all__ = ["app", "create_app"]
