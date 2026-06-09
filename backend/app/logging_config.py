"""
Structured logging configuration with correlation ID support.
All services use get_logger(__name__) to emit JSON-structured logs.
"""
import logging
import sys
from contextvars import ContextVar

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")


class CorrelationFilter(logging.Filter):
    """Injects the current correlation ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get("-")
        return True


def configure_logging(log_level: str = "INFO") -> None:
    """Set up root logger with a structured format suitable for log aggregators."""
    fmt = (
        "%(asctime)s | %(levelname)-8s | %(name)s | "
        "cid=%(correlation_id)s | %(message)s"
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))
    handler.addFilter(CorrelationFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
