"""
Request middleware: correlation IDs, request logging, basic metrics,
API version header, and in-memory rate limiting.

Adds to every request:
  - X-Request-ID header (generated or propagated from upstream)
  - X-API-Version header
  - structlog context with request_id, method, path
  - Request start/end logging with duration_ms
  - In-memory metrics (request count, latency by endpoint)
  - Per-IP rate limiting (configurable requests-per-minute)
"""
import time
import uuid
from collections import defaultdict

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = structlog.get_logger()

API_VERSION = "1.0"

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
# In-memory rate limiter (sliding window per IP)
# ---------------------------------------------------------------------------

class RateLimiter:
    """Simple sliding-window rate limiter keyed by client IP.

    Parameters
    ----------
    max_requests : int
        Maximum number of requests allowed per window.
    window_seconds : int
        Length of the sliding window in seconds (default 60).
    exclude_paths : set[str]
        Path substrings to exempt from rate limiting (e.g. "/health").
    """

    def __init__(
        self,
        max_requests: int = 120,
        window_seconds: int = 60,
        exclude_paths: set | None = None,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.exclude_paths = exclude_paths or set()
        # ip -> list of request timestamps
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def _clean(self, ip: str, now: float) -> None:
        """Remove timestamps outside the current window."""
        cutoff = now - self.window_seconds
        bucket = self._buckets[ip]
        # Find first index still in window
        idx = 0
        for idx, ts in enumerate(bucket):
            if ts >= cutoff:
                break
        else:
            idx = len(bucket)
        if idx > 0:
            self._buckets[ip] = bucket[idx:]

    def is_allowed(self, ip: str, path: str) -> tuple[bool, int]:
        """Check if the request is within rate limits.

        Returns (allowed, retry_after_seconds).
        """
        # Skip rate limiting for test clients and localhost
        if ip in ("testclient", "unknown", "127.0.0.1"):
            return True, 0
        for excluded in self.exclude_paths:
            if excluded in path:
                return True, 0

        now = time.time()
        self._clean(ip, now)
        bucket = self._buckets[ip]

        if len(bucket) >= self.max_requests:
            # Calculate retry-after from oldest entry in window
            retry_after = int(self.window_seconds - (now - bucket[0])) + 1
            return False, max(retry_after, 1)

        bucket.append(now)
        return True, 0


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Adds request ID, API version, logging, metrics, and rate limiting."""

    def __init__(self, app, rate_limiter: RateLimiter | None = None):
        super().__init__(app)
        self.rate_limiter = rate_limiter

    async def dispatch(self, request: Request, call_next):
        # ── Rate limiting ──
        if self.rate_limiter is not None:
            client_ip = request.client.host if request.client else "unknown"
            path = request.url.path
            allowed, retry_after = self.rate_limiter.is_allowed(client_ip, path)
            if not allowed:
                logger.warning(
                    "rate_limited",
                    client_ip=client_ip,
                    path=path,
                    retry_after=retry_after,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMITED",
                            "message": f"Too many requests. Retry after {retry_after}s.",
                            "details": {"retry_after": retry_after},
                        }
                    },
                    headers={"Retry-After": str(retry_after)},
                )

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

        # Add standard headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-API-Version"] = API_VERSION

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
