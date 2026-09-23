from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger("docpipeline.serverless")
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))


def log(event: str, **values: Any) -> None:
    logger.info(json.dumps({"event": event, **values}, default=str, separators=(",", ":")))
