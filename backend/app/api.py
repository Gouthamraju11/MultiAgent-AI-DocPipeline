from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings
from app.extractors import SUPPORTED_EXTENSIONS, DocumentReadError, extract_text
from app.models import HealthResponse, ProcessResponse, TextRequest
from app.pipeline import DocumentPipeline
from app.providers import build_provider

load_dotenv()
logger = logging.getLogger("docpipeline")


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings.from_env()
    provider = build_provider(resolved)
    pipeline = DocumentPipeline(provider)

    application = FastAPI(
        title="DocPipeline API",
        summary="Classify, extract, and validate structured data from business documents.",
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    application.state.settings = resolved
    application.state.pipeline = pipeline

    if resolved.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-Request-ID"],
        )

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled request error", extra={"request_id": request_id})
            raise
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = str(int((time.perf_counter() - started) * 1000))
        return response

    @application.exception_handler(DocumentReadError)
    async def document_error_handler(_: Request, exc: DocumentReadError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)})

    @application.get("/")
    async def root() -> dict[str, str]:
        return {
            "service": "DocPipeline API",
            "version": application.version,
            "status": "running",
            "docs": "/docs",
        }

    @application.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            llm_provider=provider.name,
            mode="demo" if provider.is_demo else "llm",
            max_upload_mb=max(1, (resolved.max_upload_bytes + 1024 * 1024 - 1) // (1024 * 1024)),
        )

    async def execute(text: str) -> ProcessResponse:
        started = time.perf_counter()
        try:
            stages = await run_in_threadpool(pipeline.run, text)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Pipeline provider failure")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The configured AI provider could not complete the pipeline.",
            ) from exc
        return ProcessResponse(
            job_id=uuid.uuid4().hex[:12],
            llm_provider=provider.name,
            pipeline=stages,
            processing_time_ms=int((time.perf_counter() - started) * 1000),
        )

    @application.post("/process", response_model=ProcessResponse)
    async def process_document(file: UploadFile) -> ProcessResponse:
        filename = file.filename or "document.txt"
        extension = Path(filename).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
            )
        content = await file.read(resolved.max_upload_bytes + 1)
        await file.close()
        if len(content) > resolved.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File exceeds the configured upload limit ({resolved.max_upload_bytes} bytes).",
            )
        text = await run_in_threadpool(extract_text, content, filename)
        if len(text.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Document must contain at least 10 characters of readable text.",
            )
        return await execute(text)

    @application.post("/process-text", response_model=ProcessResponse)
    async def process_text(payload: TextRequest) -> ProcessResponse:
        return await execute(payload.text)

    return application


app = create_app()
