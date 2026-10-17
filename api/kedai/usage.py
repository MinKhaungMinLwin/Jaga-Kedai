"""Gemini usage and estimated cost, one structured log line per call.

Cloud Run turns each JSON line on stdout into a structured entry in Cloud Logging, so cost can be
summed per feature, shop or visitor in Logs Explorer / Log Analytics (see docs/usage.md).
"""

import json
import sys
from contextvars import ContextVar

from kedai.tracing import log_trace_fields

# The visitor's anonymous session (X-Kedai-Session header), set per request by the API.
session_id: ContextVar[str | None] = ContextVar("session_id", default=None)

# Estimated list prices in US$ per 1M tokens (input, output incl. thinking). Check the Vertex AI pricing page;
# audio input and long prompts can cost more. Unknown models are logged with tokens but no cost.
PRICES = {
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-2.5-flash-preview-tts": (0.50, 10.00),
}


def record(feature: str, model: str, response, *, shop_id: str, project: str | None) -> dict:
    meta = getattr(response, "usage_metadata", None)
    input_tokens = getattr(meta, "prompt_token_count", None) or 0
    output_tokens = (getattr(meta, "candidates_token_count", None) or 0) + (
        getattr(meta, "thoughts_token_count", None) or 0
    )
    price = PRICES.get(model)
    cost = (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000 if price else None
    entry = {
        "severity": "INFO",
        "message": f"gemini {feature}: {input_tokens} in / {output_tokens} out tokens",
        "event": "gemini_usage",
        "feature": feature,
        "model": model,
        "shop_id": shop_id,
        "session_id": session_id.get(),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost, 8) if cost is not None else None,
        **log_trace_fields(project),
    }
    _emit(entry)
    return entry


def _emit(entry: dict) -> None:
    sys.stdout.write(json.dumps(entry, ensure_ascii=False) + "\n")
    sys.stdout.flush()
