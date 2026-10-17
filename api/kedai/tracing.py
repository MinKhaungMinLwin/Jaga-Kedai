"""Google Cloud Trace: one trace per shopkeeper action, Gemini calls inside it.

Off unless KEDAI_CLOUD_TRACE is set (deploy.sh sets it on Cloud Run). Without it, spans are no-ops.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace

logger = logging.getLogger(__name__)
_configured = False


def configure_tracing(settings) -> None:
    global _configured
    if _configured or not settings.cloud_trace or not settings.gcp_project:
        return
    try:
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": "jaga-kedai-api"}))
        provider.add_span_processor(
            BatchSpanProcessor(CloudTraceSpanExporter(project_id=settings.gcp_project))
        )
        trace.set_tracer_provider(provider)
    except Exception as exc:  # The app must keep working if tracing cannot start.
        logger.warning("Cloud Trace unavailable: %s", exc)
    _configured = True


def flush() -> None:
    """Send buffered spans now: Cloud Run only gives the instance CPU while a request is running."""
    if not _configured:
        return
    try:
        trace.get_tracer_provider().force_flush(timeout_millis=3000)
    except Exception as exc:  # Never fail a request because a trace could not be sent.
        logger.warning("Trace flush failed: %s", exc)


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[trace.Span]:
    with trace.get_tracer("jaga-kedai").start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value)
        yield current


def log_trace_fields(project: str | None) -> dict[str, str]:
    """Fields that make Cloud Logging link a log line to the current Cloud Trace span."""
    context = trace.get_current_span().get_span_context()
    if not project or not context.is_valid:
        return {}
    return {
        "logging.googleapis.com/trace": f"projects/{project}/traces/{context.trace_id:032x}",
        "logging.googleapis.com/spanId": f"{context.span_id:016x}",
    }
