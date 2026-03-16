"""
HTTP Basic Auth for the comment analysis backend.

Reads credentials from COMMENT_USER/COMMENT_PASS, falling back to
PIPELINE_USER/PIPELINE_PASS so both backends can share one credential set.
"""
import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

COMMENT_USER = os.environ.get("COMMENT_USER") or os.environ.get("PIPELINE_USER", "")
COMMENT_PASS = os.environ.get("COMMENT_PASS") or os.environ.get("PIPELINE_PASS", "")


def verify_comment_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """Validate HTTP Basic credentials.

    Returns the authenticated username on success.
    Raises 401 on failure, 503 if credentials not configured.
    """
    if not COMMENT_USER or not COMMENT_PASS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication not configured. Set COMMENT_USER/COMMENT_PASS or PIPELINE_USER/PIPELINE_PASS.",
        )

    correct_user = secrets.compare_digest(
        credentials.username.encode(), COMMENT_USER.encode()
    )
    correct_pass = secrets.compare_digest(
        credentials.password.encode(), COMMENT_PASS.encode()
    )

    if correct_user and correct_pass:
        return credentials.username

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Basic"},
    )
