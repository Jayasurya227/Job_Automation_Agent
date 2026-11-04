"""
Module: llm.py
Purpose: Shared helpers for reading Claude API responses and parsing JSON replies.
Standards: Rule 2 (Type Safety), Rule 5 (Production Reliability).
"""
import json
import re
from typing import Any, Dict


def response_text(response: Any) -> str:
    """Returns the concatenated text blocks of a Claude response (skips thinking blocks)."""
    return "".join(block.text for block in response.content if block.type == "text").strip()


def parse_json_object(raw_text: str) -> Dict[str, Any]:
    """Parses a JSON object from model output, tolerating ```json fences and surrounding prose."""
    text = (raw_text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in AI response: {text[:200]}")
        return json.loads(match.group(0))
