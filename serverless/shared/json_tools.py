from __future__ import annotations

import json
import re
from typing import Any


def parse_json_object(raw: str) -> dict[str, Any]:
    """Extract the first valid JSON object from an LLM response."""
    clean = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
    decoder = json.JSONDecoder()
    for index, character in enumerate(clean):
        if character != "{":
            continue
        try:
            result, _ = decoder.raw_decode(clean[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(result, dict):
            return result
    raise ValueError("Bedrock did not return a valid JSON object")


def message_text(content: object) -> str:
    """Normalize LangChain's string and content-block response variants."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "".join(parts)
    raise ValueError("Bedrock returned an unsupported response format")
