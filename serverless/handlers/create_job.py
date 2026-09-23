from __future__ import annotations

import json
import os
import re
import time
import uuid

from shared.aws import s3_client, table
from shared.config import MAX_DOCUMENT_BYTES, document_bucket
from shared.documents import SUPPORTED_EXTENSIONS
from shared.logging import log


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json", "cache-control": "no-store"},
        "body": json.dumps(body),
    }


def lambda_handler(event: dict, _context: object) -> dict:
    try:
        payload = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "Request body must be valid JSON"})

    filename = os.path.basename(str(payload.get("filename") or "")).strip()
    extension = os.path.splitext(filename)[1].lower()
    if not filename or extension not in SUPPORTED_EXTENSIONS:
        return _response(400, {"error": f"filename must use one of: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"})
    content_type = str(payload.get("content_type") or "application/octet-stream")[:120]
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[:180]
    job_id = uuid.uuid4().hex
    now = int(time.time())
    key = f"uploads/{job_id}/{safe_name}"

    table().put_item(
        Item={
            "job_id": job_id,
            "status": "AWAITING_UPLOAD",
            "filename": safe_name,
            "source_key": key,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + (7 * 24 * 60 * 60),
            "audit_trail": [{"stage": "intake", "status": "created", "at": now}],
        },
        ConditionExpression="attribute_not_exists(job_id)",
    )
    upload_url = s3_client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": document_bucket(),
            "Key": key,
            "ContentType": content_type,
            "ServerSideEncryption": "AES256",
        },
        ExpiresIn=900,
    )
    log("job_created", job_id=job_id, key=key)
    return _response(
        201,
        {
            "job_id": job_id,
            "status": "AWAITING_UPLOAD",
            "upload_url": upload_url,
            "upload_headers": {"Content-Type": content_type, "x-amz-server-side-encryption": "AES256"},
            "max_upload_bytes": MAX_DOCUMENT_BYTES,
            "expires_in_seconds": 900,
        },
    )
