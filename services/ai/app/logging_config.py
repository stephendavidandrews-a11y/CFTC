"""
Structured logging configuration using structlog.

Usage in any module:
    import structlog
    logger = structlog.get_logger()
    logger.info("event_name", key="value")

Request-scoped context (request_id, user) is automatically bound
by the request ID middleware and available in all log events.
"""

import logging
import os
import sys

import structlog


def setup_logging(service_name: str = "cftc") -> None:
    """Configure structlog for the service.

    JSON output in production (ENVIRONMENT != "development"),
    human-readable colored output in development.
    """
    env = os.environ.get("ENVIRONMENT", "development")
    is_dev = env == "development"
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    # Shared processors for all output modes
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if is_dev:
        # Human-readable colored output for development
        renderer = structlog.dev.ConsoleRenderer()
    else:
        # JSON output for production (machine-parseable)
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to use structlog formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Quiet noisy third-party loggers
    for noisy in ("uvicorn.access", "watchdog", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    structlog.get_logger().info(
        "logging_configured",
        service=service_name,
        environment=env,
        log_level=log_level,
        renderer="console" if is_dev else "json",
    )
