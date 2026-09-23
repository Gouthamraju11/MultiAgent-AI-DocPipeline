from __future__ import annotations

import json
import os
import random
import time
from decimal import Decimal
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError
from shared.config import document_bucket, table_name
from shared.logging import log


@lru_cache(maxsize=1)
def table():
    return boto3.resource("dynamodb").Table(table_name())


@lru_cache(maxsize=1)
def s3_client():
    return boto3.client("s3")


@lru_cache(maxsize=1)
def sqs_client():
    return boto3.client("sqs")


def get_job(job_id: str) -> dict[str, Any]:
    return table().get_item(Key={"job_id": job_id}, ConsistentRead=True).get("Item", {})


def stage_output(job_id: str, output_field: str) -> object | None:
    return get_job(job_id).get(output_field)


def to_dynamo(value: object) -> object:
    """DynamoDB rejects Python floats; preserve numeric precision as Decimal."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [to_dynamo(item) for item in value]
    if isinstance(value, dict):
        return {key: to_dynamo(item) for key, item in value.items()}
    return value


def mark_stage_running(job_id: str, stage: str, output_field: str) -> bool:
    """Return False when this stage was already committed by an earlier delivery."""
    try:
        table().update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #status=:status, updated_at=:now ADD #attempts :one",
            ConditionExpression="attribute_not_exists(#output)",
            ExpressionAttributeNames={
                "#status": "status",
                "#attempts": f"{stage}_attempts",
                "#output": output_field,
            },
            ExpressionAttributeValues={
                ":status": f"{stage.upper()}_RUNNING",
                ":now": int(time.time()),
                ":one": 1,
            },
        )
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            log("duplicate_delivery", job_id=job_id, stage=stage)
            return False
        raise


def complete_stage(job_id: str, stage: str, output_field: str, output: object, next_status: str) -> None:
    event = {"stage": stage, "status": "complete", "at": int(time.time())}
    table().update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #output=:output, #status=:status, updated_at=:now, audit_trail=list_append(if_not_exists(audit_trail,:empty),:event)",
        ExpressionAttributeNames={"#output": output_field, "#status": "status"},
        ExpressionAttributeValues={
            ":output": to_dynamo(output),
            ":status": next_status,
            ":now": int(time.time()),
            ":empty": [],
            ":event": [event],
        },
    )


def fail_job(job_id: str, stage: str, error: Exception) -> None:
    safe_message = f"{type(error).__name__}: {str(error)[:300]}"
    table().update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #status=:status, last_error=:error, failed_stage=:stage, updated_at=:now",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": f"{stage.upper()}_RETRYING",
            ":error": safe_message,
            ":stage": stage,
            ":now": int(time.time()),
        },
    )


def send(queue_url: str, payload: dict[str, Any]) -> None:
    sqs_client().send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(payload, separators=(",", ":")),
        MessageAttributes={
            "job_id": {"DataType": "String", "StringValue": str(payload["job_id"])},
            "correlation_id": {"DataType": "String", "StringValue": str(payload.get("correlation_id", payload["job_id"]))},
        },
    )


def put_text(job_id: str, text: str) -> str:
    key = f"artifacts/{job_id}/source.txt"
    s3_client().put_object(
        Bucket=document_bucket(),
        Key=key,
        Body=text.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
        ServerSideEncryption="AES256",
    )
    return key


def get_bytes(key: str) -> bytes:
    return s3_client().get_object(Bucket=document_bucket(), Key=key)["Body"].read()


def get_text(key: str) -> str:
    return get_bytes(key).decode("utf-8")


def extend_visibility(record: dict[str, Any]) -> None:
    queue_url = os.getenv("SOURCE_QUEUE_URL")
    receipt = record.get("receiptHandle")
    if not queue_url or not receipt:
        return
    receive_count = int(record.get("attributes", {}).get("ApproximateReceiveCount", "1"))
    delay = min(900, (2 ** min(receive_count, 7)) * 5 + random.randint(0, 5))
    sqs_client().change_message_visibility(QueueUrl=queue_url, ReceiptHandle=receipt, VisibilityTimeout=delay)


def batch_handler(event: dict[str, Any], stage: str, processor) -> dict[str, list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    for record in event.get("Records", []):
        message_id = record.get("messageId", "unknown")
        job_id = "unknown"
        try:
            payload = json.loads(record["body"])
            job_id = str(payload.get("job_id") or _s3_job_id(payload) or job_id)
            processor(payload)
        except Exception as exc:
            log("stage_failed", stage=stage, job_id=job_id, message_id=message_id, error=repr(exc))
            if job_id != "unknown":
                try:
                    fail_job(job_id, stage, exc)
                except Exception as state_error:
                    log("failure_state_write_failed", job_id=job_id, error=repr(state_error))
            try:
                extend_visibility(record)
            except Exception as visibility_error:
                log("visibility_update_failed", message_id=message_id, error=repr(visibility_error))
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}


def _s3_job_id(payload: dict[str, Any]) -> str | None:
    try:
        key = payload["Records"][0]["s3"]["object"]["key"]
        parts = key.split("/", 2)
        return parts[1] if len(parts) == 3 and parts[0] == "uploads" else None
    except (KeyError, IndexError, TypeError):
        return None
