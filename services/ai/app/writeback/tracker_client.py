"""HTTP client for POST /tracker/batch with retry, idempotency, and error handling."""

import logging
import asyncio

import httpx

from app.config import TRACKER_BASE_URL, TRACKER_USER, TRACKER_PASS

logger = logging.getLogger(__name__)

# Retry config
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = [1.0, 3.0]
TIMEOUT_SECONDS = 30.0


class TrackerBatchError(Exception):
    """Raised when a tracker batch call fails."""
    def __init__(self, status_code: int, error_type: str, message: str,
                 operation_index: int | None = None):
        self.status_code = status_code
        self.error_type = error_type
        self.message = message
        self.operation_index = operation_index
        super().__init__(f"[{status_code}] {error_type}: {message}")


class TrackerIdempotencyConflict(TrackerBatchError):
    """Same idempotency key used with different payload."""
    pass


async def post_batch(operations: list[dict],
                     source: str = "ai",
                     source_metadata: dict | None = None,
                     idempotency_key: str | None = None) -> dict:
    """Send a batch of operations to POST /tracker/batch.

    Returns the tracker response dict on success.
    Raises TrackerBatchError on failure after retries.
    """
    url = f"{TRACKER_BASE_URL}/batch"
    payload = {
        "operations": operations,
        "source": source,
        "source_metadata": source_metadata or {},
    }
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key

    auth = None
    if TRACKER_USER and TRACKER_PASS:
        auth = (TRACKER_USER, TRACKER_PASS)

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.post(url, json=payload, auth=auth)

            if resp.status_code == 200:
                return resp.json()

            # Parse error detail
            try:
                detail = resp.json().get("detail", {})
            except Exception:
                detail = {"error_type": "unknown", "message": resp.text}

            error_type = detail.get("error_type", "unknown")
            message = detail.get("message", str(resp.status_code))
            op_index = detail.get("operation_index")

            # 409 idempotency conflict — do not retry
            if resp.status_code == 409:
                raise TrackerIdempotencyConflict(
                    409, error_type, message, op_index)

            # 4xx — do not retry (bad data)
            if 400 <= resp.status_code < 500:
                raise TrackerBatchError(
                    resp.status_code, error_type, message, op_index)

            # 5xx — retry
            last_error = TrackerBatchError(
                resp.status_code, error_type, message, op_index)
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_SECONDS[attempt]
                logger.warning("Tracker batch 5xx (attempt %d/%d), retrying in %.1fs: %s",
                               attempt + 1, MAX_RETRIES + 1, wait, message)
                await asyncio.sleep(wait)
                continue
            raise last_error

        except (httpx.ConnectError, httpx.TimeoutException, OSError) as e:
            last_error = TrackerBatchError(0, "connection_error", str(e))
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_SECONDS[attempt]
                logger.warning("Tracker unreachable (attempt %d/%d), retrying in %.1fs: %s",
                               attempt + 1, MAX_RETRIES + 1, wait, e)
                await asyncio.sleep(wait)
                continue
            raise last_error

    raise last_error  # Should not reach here
