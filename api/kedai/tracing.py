"""Optional Arize Phoenix tracing: one trace per shopkeeper action, Gemini calls nested inside."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace

logger = logging.getLogger(__name__)
_configured = False


def configure_tracing(settings) -> None:
    global _configured
    if _configured or not settings.phoenix_endpoint:
        return
    from openinference.instrumentation import TraceConfig
    from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
    from phoenix.otel import register

    provider = register(
        endpoint=settings.phoenix_endpoint,
        project_name=settings.phoenix_project,
        api_key=settings.phoenix_api_key,
        protocol="http/protobuf",
        batch=True,
        verbose=False,
    )
    hide = not settings.trace_content
    try:
        GoogleGenAIInstrumentor().instrument(
            tracer_provider=provider,
            config=TraceConfig(
                hide_inputs=hide,
                hide_outputs=hide,
                hide_input_messages=hide,
                hide_output_messages=hide,
                hide_input_text=hide,
                hide_output_text=hide,
                hide_input_images=True,
            ),
        )
    except Exception as exc:  # The app must keep working if instrumentation is incompatible.
        logger.warning("Gemini auto-instrumentation unavailable: %s", exc)
    _configured = True


@contextmanager
def span(name: str, kind: str = "CHAIN", **attributes: Any) -> Iterator[trace.Span]:
    with trace.get_tracer("kedai-kaki").start_as_current_span(name) as current:
        current.set_attribute("openinference.span.kind", kind)
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value)
        yield current
