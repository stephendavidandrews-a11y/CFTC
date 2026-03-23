"""
Request middleware: correlation IDs, request logging, and basic metrics.

Adds to every request:
  - X-Request-ID header (generated or propagated from upstream)
  - structlog context with request_id, method, path
  - Request start/end logging with duration_ms
  - In-memory metrics (request count, latency by endpoint)
"""
import time
import uuid
from collections import defaultdict

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# In-memory metrics store
# ---------------------------------------------------------------------------

class RequestMetrics:
    """Simple in-memory request metrics. Thread-safe enough for single-process."""

    def __init__(self):
        self.counts = defaultdict(int)       # (method, path, status) -> count
        self.latencies = defaultdict(list)    # (method, path) -> [ms, ...]
        self._max_latencies = 1000           # keep last N per endpoint

    def record(self, method: str, path: str, status: int, duration_ms: float):
        key = (method, path, status)
        self.counts[key] += 1
        lat_key = (method, path)
        bucket = self.latencies[lat_key]
        bucket.append(duration_ms)
        if len(bucket) > self._max_latencies:
            self.latencies[lat_key] = bucket[-self._max_latencies:]

    def snapshot(self) -> dict:
        """Return a JSON-serializable snapshot of current metrics."""
        endpoints = {}
        for (method, path, status), count in sorted(self.counts.items()):
            key = f"{method} {path}"
            if key not in endpoints:
                endpoints[key] = {"total": 0, "by_status": {}, "latency_ms": {}}
            endpoints[key]["total"] += count
            endpoints[key]["by_status"][str(status)] = count

        for (method, path), latencies in self.latencies.items():
            key = f"{method} {path}"
            if key in endpoints and latencies:
                sorted_lat = sorted(latencies)
                n = len(sorted_lat)
                endpoints[key]["latency_ms"] = {
                    "p50": sorted_lat[n // 2],
                    "p95": sorted_lat[int(n * 0.95)] if n >= 20 else None,
                    "p99": sorted_lat[int(n * 0.99)] if n >= 100 else None,
                    "count": n,
                }

        return {"endpoints": endpoints}


# Singleton metrics store — one per process
metrics = RequestMetrics()


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Adds request ID, logging, and metrics to every request."""

    async def dispatch(self, request: Request, call_next):
        # Generate or propagate request ID
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        # Normalize path for metrics (collapse UUIDs to {id})
        path = request.url.path
        metric_path = _normalize_path(path)

        # Bind to structlog context for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=path,
        )

        start = time.perf_counter()

        try:
            response: Response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            metrics.record(request.method, metric_path, 500, duration_ms)
            logger.exception("request_error", duration_ms=round(duration_ms, 1))
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        metrics.record(request.method, metric_path, response.status_code, duration_ms)

        # Add request ID to response
        response.headers["X-Request-ID"] = request_id

        # Log completed request (skip health checks to reduce noise)
        if "/health" not in path and "/metrics" not in path:
            logger.info(
                "request_completed",
                status=response.status_code,
                duration_ms=round(duration_ms, 1),
            )

        return response


def _normalize_path(path: str) -> str:
    """Collapse UUID-like path segments to {id} for metric grouping."""
    parts = path.split("/")
    normalized = []
    for part in parts:
        # UUIDs are 36 chars with hyphens, or 32 hex chars
        if len(part) >= 32 and all(c in "0123456789abcdef-" for c in part.lower()):
            normalized.append("{id}")
        else:
            normalized.append(part)
    return "/".join(normalized)
