from __future__ import annotations

import json
from decimal import Decimal

from shared.aws import get_job


class DecimalEncoder(json.JSONEncoder):
    def default(self, value):
        if isinstance(value, Decimal):
            return int(value) if value % 1 == 0 else float(value)
        return super().default(value)


def lambda_handler(event: dict, _context: object) -> dict:
    job_id = str(event.get("pathParameters", {}).get("job_id") or "")
    job = get_job(job_id) if job_id else {}
    if not job:
        return {"statusCode": 404, "headers": {"content-type": "application/json"}, "body": '{"error":"Job not found"}'}
    job.pop("source_key", None)
    job.pop("text_key", None)
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json", "cache-control": "no-store"},
        "body": json.dumps(job, cls=DecimalEncoder),
    }
