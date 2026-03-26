"""Shared request-scoped dependencies for tracker routers."""

from fastapi import Request


def get_write_source(request: Request) -> str:
    """Extract write source from X-Write-Source header. Defaults to 'human'."""
    return request.headers.get("x-write-source", "human")
