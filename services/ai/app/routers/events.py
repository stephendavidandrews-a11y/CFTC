"""SSE endpoint for pipeline progress updates."""
import asyncio
import json
import logging
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["events"])

# In-memory event bus (single-process; upgrade to Redis pub/sub if multi-process)
_subscribers: list[asyncio.Queue] = []


async def publish_event(event_type: str, data: dict):
    """Publish an event to all connected SSE clients.

    Stores both the event_type (for SSE named events) and the JSON payload.
    """
    payload = json.dumps({"type": event_type, **data})
    message = (event_type, payload)  # tuple: (name, data)
    dead = []
    for q in _subscribers:
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        _subscribers.remove(q)


@router.get("/stream")
async def event_stream(request: Request):
    """SSE stream for pipeline progress updates."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.append(queue)

    async def generate():
        try:
            yield "retry: 5000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                    event_name, payload = message
                    yield f"event: {event_name}\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in _subscribers:
                _subscribers.remove(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
