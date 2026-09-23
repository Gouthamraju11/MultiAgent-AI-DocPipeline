from __future__ import annotations

import os

from shared.aws import (
    batch_handler,
    complete_stage,
    get_text,
    mark_stage_running,
    send,
    stage_output,
)
from shared.logging import log
from shared.pipeline import extract


def process(payload: dict) -> None:
    job_id = str(payload["job_id"])
    output = stage_output(job_id, "extraction")
    if output is None:
        if mark_stage_running(job_id, "extract", "extraction"):
            output = extract(get_text(str(payload["text_key"])), str(payload["doc_type"]))
            complete_stage(job_id, "extract", "extraction", output, "VALIDATION_QUEUED")
        else:
            output = stage_output(job_id, "extraction")
            if not isinstance(output, dict):
                raise RuntimeError("A concurrent extraction is still running")
    send(
        os.environ["NEXT_QUEUE_URL"],
        {"job_id": job_id, "doc_type": payload["doc_type"], "correlation_id": payload.get("correlation_id", job_id)},
    )
    log("extraction_complete", job_id=job_id, fields=len(output))


def lambda_handler(event: dict, _context: object) -> dict:
    return batch_handler(event, "extract", process)
