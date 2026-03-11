"""
Async wrapper for synchronous SQLite operations.

Since the pipeline module uses sqlite3 (synchronous) but FastAPI is async,
we wrap DB calls in run_in_executor to avoid blocking the event loop.
"""

import asyncio
from functools import partial


async def run_db(func, *args, **kwargs):
    """
    Run a synchronous DB function in a thread executor.

    Usage:
        result = await run_db(some_sync_function, arg1, arg2)
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))
