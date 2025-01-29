"""Telemetry components for the FFC Framework."""

import logging
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional

from .schema import TelemetryConfig


@dataclass
class TelemetryEvent:
    """Represents a telemetry event."""

    event_type: str
    timestamp: float
    data: dict[str, Any]
    source: str
    level: str = "INFO"


class TelemetryManager:
    """Manages telemetry collection and reporting."""

    def __init__(self, config: TelemetryConfig | None = None) -> None:
        """Initialize telemetry manager.

        Args:
            config: Telemetry configuration
        """
        self.config = config or TelemetryConfig()
        self._events: list[TelemetryEvent] = []
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger("ffc.telemetry")

    def emit_event(
        self,
        event_type: str,
        data: dict[str, Any],
        source: str,
        level: str = "INFO",
    ) -> None:
        """Emit a telemetry event.

        Args:
            event_type: Type of event
            data: Event data
            source: Event source
            level: Event level
        """
        if not self.config.enabled:
            return

        event = TelemetryEvent(
            event_type=event_type,
            timestamp=time.time(),
            data=data,
            source=source,
            level=level,
        )
        self._events.append(event)

        # Log the event
        log_level = getattr(logging, level)
        self.logger.log(
            log_level,
            "Telemetry event: %s from %s: %s",
            event_type,
            source,
            data,
        )

    def record_llm_operation(
        self,
        provider: str,
        operation: str,
        model: str,
        token_usage: Any,
        duration: timedelta,
        error: Optional[Exception] = None,
    ) -> None:
        """Record telemetry for an LLM operation.

        Args:
            provider: Name of the LLM provider
            operation: Operation type (completion, chat, embedding)
            model: Model used
            token_usage: Token usage statistics
            duration: Operation duration
            error: Optional error that occurred
        """
        data = {
            "provider": provider,
            "operation": operation,
            "model": model,
            "token_usage": token_usage.__dict__,
            "duration_ms": duration.total_seconds() * 1000,
        }
        if error:
            data["error"] = str(error)
            level = "ERROR"
        else:
            level = "INFO"

        self.emit_event("llm_operation", data, source="llm", level=level)

    def record_metric(self, name: str, metadata: dict[str, Any]) -> None:
        """Record a metric with metadata.

        Args:
            name: Name of the metric
            metadata: Metric metadata
        """
        self.emit_event(f"metric.{name}", metadata, source="metrics")

    def get_events(
        self,
        event_type: str | None = None,
        source: str | None = None,
        level: str | None = None,
    ) -> list[TelemetryEvent]:
        """Get telemetry events matching the filters.

        Args:
            event_type: Filter by event type
            source: Filter by source
            level: Filter by level

        Returns:
            List of matching events
        """
        events = self._events
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if source:
            events = [e for e in events if e.source == source]
        if level:
            events = [e for e in events if e.level == level]
        return events

    def clear_events(self) -> None:
        """Clear all telemetry events."""
        self._events.clear()
