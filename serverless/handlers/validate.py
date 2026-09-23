from __future__ import annotations

from shared.aws import batch_handler, complete_stage, get_job, mark_stage_running, stage_output
from shared.logging import log
from shared.pipeline import validate


def process(payload: dict) -> None:
    job_id = str(payload["job_id"])
    output = stage_output(job_id, "validation")
    if output is None:
        if mark_stage_running(job_id, "validate", "validation"):
            extraction = get_job(job_id).get("extraction")
            if not isinstance(extraction, dict):
                raise ValueError("Extraction output is missing")
            output = validate(extraction, str(payload["doc_type"]))
            complete_stage(job_id, "validate", "validation", output, "COMPLETE")
        else:
            output = stage_output(job_id, "validation")
            if not isinstance(output, dict):
                raise RuntimeError("A concurrent validation is still running")
    log("validation_complete", job_id=job_id, valid=output.get("valid"))


def lambda_handler(event: dict, _context: object) -> dict:
    return batch_handler(event, "validate", process)
