from __future__ import annotations

import os
import urllib.parse

from shared.aws import (
    batch_handler,
    complete_stage,
    get_bytes,
    mark_stage_running,
    put_text,
    send,
    stage_output,
)
from shared.documents import extract_text
from shared.logging import log
from shared.pipeline import classify


def _s3_payload(payload: dict) -> tuple[str, str, str]:
    # S3 sends an event envelope as the SQS message body.
    record = payload["Records"][0]
    key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
    parts = key.split("/", 2)
    if len(parts) != 3 or parts[0] != "uploads":
        raise ValueError("Unexpected S3 object key")
    return parts[1], key, parts[2]


def process(payload: dict) -> None:
    job_id, key, filename = _s3_payload(payload)
    previous = stage_output(job_id, "classification")
    if previous is None:
        if mark_stage_running(job_id, "classify", "classification"):
            text = extract_text(get_bytes(key), filename)
            if len(text.strip()) < 10:
                raise ValueError("Document contains fewer than 10 readable characters")
            output = classify(text)
            text_key = put_text(job_id, text)
            output["text_key"] = text_key
            complete_stage(job_id, "classify", "classification", output, "EXTRACTION_QUEUED")
        else:
            output = stage_output(job_id, "classification")
            if not isinstance(output, dict):
                raise RuntimeError("A concurrent classification is still running")
            text_key = output["text_key"]
    else:
        output = previous
        text_key = output["text_key"]
    send(
        os.environ["NEXT_QUEUE_URL"],
        {"job_id": job_id, "text_key": text_key, "doc_type": output["doc_type"], "correlation_id": job_id},
    )
    log("classification_complete", job_id=job_id, doc_type=output["doc_type"])


def lambda_handler(event: dict, _context: object) -> dict:
    return batch_handler(event, "classify", process)
