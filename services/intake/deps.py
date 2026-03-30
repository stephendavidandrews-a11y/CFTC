"""FastAPI dependencies — auth."""
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from config import PIPELINE_USER, PIPELINE_PASS

_security = HTTPBasic()


def verify_auth(credentials: HTTPBasicCredentials = Depends(_security)):
    """Require valid HTTP Basic credentials. Rejects if creds not configured."""
    if not PIPELINE_USER or not PIPELINE_PASS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth not configured — set PIPELINE_USER and PIPELINE_PASS",
        )
    ok_user = secrets.compare_digest(
        credentials.username.encode(), PIPELINE_USER.encode()
    )
    ok_pass = secrets.compare_digest(
        credentials.password.encode(), PIPELINE_PASS.encode()
    )
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
