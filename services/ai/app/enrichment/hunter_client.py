"""Hunter.io HTTP client — rate limited, retrying, cached.

Endpoints used:
  GET /v2/email-finder     name + domain -> email        (1 credit)
  GET /v2/combined/find    email -> linkedin/title/etc   (1 credit)
  GET /v2/account          remaining credits             (free)
  GET /v2/email-count      per-domain estimate           (free)

Three rules this module exists to enforce:
  1. The API key is never logged, never returned, never put in an error message.
  2. A cache hit costs zero credits.
  3. "Not found" is a real answer, not an error — record it and move on.
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx

from app.config import HUNTER_API_KEY, load_policy

logger = logging.getLogger(__name__)

HUNTER_BASE_URL = "https://api.hunter.io/v2"

# Retry policy: 429 and 5xx only. Any other 4xx is terminal for that row.
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = [1.0, 2.0, 4.0]
TIMEOUT_SECONDS = 20.0

ENDPOINT_EMAIL_FINDER = "email_finder"
ENDPOINT_COMBINED = "combined_enrichment"


class HunterError(Exception):
    """A Hunter call failed in a way that is terminal for the row."""

    def __init__(self, status_code: int, message: str, retryable: bool = False):
        self.status_code = status_code
        self.message = message
        self.retryable = retryable
        super().__init__(f"[{status_code}] {message}")


class HunterAuthError(HunterError):
    """Bad or missing API key — fails the whole job, not just a row."""


class HunterRateLimiter:
    """Token bucket, shared across all calls in a process.

    Hunter allows roughly 15 req/s on paid plans; the policy default of 8 leaves
    headroom so a burst does not trip the limit in the first place.
    """

    def __init__(self, rate_per_second: float):
        self.rate = max(0.1, float(rate_per_second))
        self._lock = asyncio.Lock()
        self._next_slot = 0.0

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            wait = self._next_slot - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._next_slot = max(now, self._next_slot) + (1.0 / self.rate)


@dataclass
class HunterResult:
    """Outcome of a single enrichment lookup."""

    status: str  # 'found' | 'not_found' | 'error'
    email: str | None = None
    score: int | None = None
    verification: str | None = None
    position: str | None = None
    linkedin_url: str | None = None
    twitter: str | None = None
    seniority: str | None = None
    department: str | None = None
    sources_count: int | None = None
    raw: dict = field(default_factory=dict)
    from_cache: bool = False
    credits_used: int = 0
    error_detail: str | None = None


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def _cache_key(endpoint: str, **parts) -> str:
    """Stable hash of the lookup, so the same person is never paid for twice."""
    payload = endpoint + "|" + "|".join(
        f"{k}={(parts.get(k) or '').strip().lower()}" for k in sorted(parts)
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def cache_get(db, lookup_key: str) -> dict | None:
    """Return the cached response for this key, or None. Expired rows miss."""
    row = db.execute(
        "SELECT response_json, expires_at FROM enrichment_cache WHERE lookup_key = ?",
        (lookup_key,),
    ).fetchone()
    if not row:
        return None
    if row["expires_at"]:
        try:
            if datetime.fromisoformat(row["expires_at"]) < datetime.now():
                return None
        except ValueError:
            pass
    db.execute(
        "UPDATE enrichment_cache SET hit_count = hit_count + 1 WHERE lookup_key = ?",
        (lookup_key,),
    )
    try:
        return json.loads(row["response_json"])
    except (TypeError, json.JSONDecodeError):
        return None


def cache_put(db, lookup_key: str, endpoint: str, response: dict, ttl_days: int):
    """Store a response. A TTL of 0 or less means never expire."""
    expires_at = None
    if ttl_days and ttl_days > 0:
        expires_at = (datetime.now() + timedelta(days=ttl_days)).isoformat()
    db.execute(
        """INSERT INTO enrichment_cache (id, lookup_key, endpoint, response_json, expires_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(lookup_key) DO UPDATE SET
               response_json = excluded.response_json,
               endpoint = excluded.endpoint,
               fetched_at = datetime('now'),
               expires_at = excluded.expires_at""",
        (str(uuid.uuid4()), lookup_key, endpoint, json.dumps(response), expires_at),
    )


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _redact(text: str) -> str:
    """Strip the API key from anything headed for a log or an exception."""
    if not text:
        return text
    if HUNTER_API_KEY:
        text = text.replace(HUNTER_API_KEY, "***")
    return text


class HunterClient:
    """Async Hunter client. One instance per job run."""

    def __init__(self, api_key: str | None = None, policy: dict | None = None):
        self.api_key = api_key if api_key is not None else HUNTER_API_KEY
        pol = (policy or load_policy()).get("enrichment_policy", {})
        self.limiter = HunterRateLimiter(pol.get("requests_per_second", 8))
        self.cache_ttl_days = pol.get("cache_ttl_days", 90)
        self._client: httpx.AsyncClient | None = None
        self._owns_client = False

    async def __aenter__(self):
        # Do not clobber a client that was injected (tests supply a transport).
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
            self._owns_client = True
        return self

    async def __aexit__(self, *exc):
        if self._client and getattr(self, "_owns_client", False):
            await self._client.aclose()
            self._client = None
            self._owns_client = False

    def _require_key(self):
        if not self.api_key:
            raise HunterAuthError(401, "HUNTER_API_KEY is not configured")

    async def _get(self, path: str, params: dict) -> dict:
        """One GET with rate limiting and retries. Returns the parsed JSON body.

        Raises HunterAuthError on 401/403 (fails the job) and HunterError on any
        other terminal status.
        """
        self._require_key()
        if self._client is None:
            raise RuntimeError("HunterClient used outside its async context")

        url = f"{HUNTER_BASE_URL}{path}"
        query = dict(params)
        query["api_key"] = self.api_key

        last_error: HunterError | None = None
        for attempt in range(MAX_ATTEMPTS):
            await self.limiter.acquire()
            try:
                resp = await self._client.get(url, params=query)
            except (httpx.ConnectError, httpx.TimeoutException, OSError) as e:
                last_error = HunterError(0, _redact(str(e)), retryable=True)
                if attempt < MAX_ATTEMPTS - 1:
                    await asyncio.sleep(BACKOFF_SECONDS[attempt])
                    continue
                raise last_error

            if resp.status_code == 200:
                return resp.json()

            detail = _redact(self._error_message(resp))

            if resp.status_code in (401, 403):
                raise HunterAuthError(resp.status_code, detail)

            # 404 from email-finder means "no email found", which callers treat
            # as a real answer rather than a failure.
            if resp.status_code == 404:
                raise HunterError(404, detail)

            if resp.status_code == 429:
                wait = self._retry_after(resp, attempt)
                last_error = HunterError(429, detail, retryable=True)
                if attempt < MAX_ATTEMPTS - 1:
                    logger.warning(
                        "Hunter 429 (attempt %d/%d), waiting %.1fs",
                        attempt + 1,
                        MAX_ATTEMPTS,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise last_error

            if resp.status_code >= 500:
                last_error = HunterError(resp.status_code, detail, retryable=True)
                if attempt < MAX_ATTEMPTS - 1:
                    await asyncio.sleep(BACKOFF_SECONDS[attempt])
                    continue
                raise last_error

            # Any other 4xx is terminal for this row.
            raise HunterError(resp.status_code, detail)

        raise last_error or HunterError(0, "exhausted retries")

    @staticmethod
    def _error_message(resp: httpx.Response) -> str:
        """Pull Hunter's error text out of the body, falling back to the status."""
        try:
            body = resp.json()
        except (ValueError, TypeError):
            return resp.text or f"HTTP {resp.status_code}"
        errors = body.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                return first.get("details") or first.get("code") or str(first)
            return str(first)
        return body.get("message") or f"HTTP {resp.status_code}"

    @staticmethod
    def _retry_after(resp: httpx.Response, attempt: int) -> float:
        """Honour Retry-After when Hunter sends it, else back off."""
        header = resp.headers.get("Retry-After")
        if header:
            try:
                return max(0.0, float(header))
            except ValueError:
                pass
        return BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]

    # -- free endpoints ----------------------------------------------------

    async def account(self) -> dict:
        """Remaining credits. Free, and the pre-flight spend guard."""
        body = await self._get("/account", {})
        return body.get("data", {})

    async def email_count(self, domain: str) -> dict:
        """How many emails Hunter knows for a domain. Free — no api_key needed,
        but sending it is harmless and keeps one code path."""
        body = await self._get("/email-count", {"domain": domain})
        return body.get("data", {})

    # -- paid endpoints ----------------------------------------------------

    async def find_email(
        self, db, first_name: str, last_name: str, domain: str
    ) -> HunterResult:
        """Email Finder. Checks the cache first; a hit costs no credit."""
        key = _cache_key(
            ENDPOINT_EMAIL_FINDER,
            first=first_name,
            last=last_name,
            domain=domain,
        )
        cached = cache_get(db, key)
        if cached is not None:
            result = self._parse_finder(cached)
            result.from_cache = True
            result.credits_used = 0
            return result

        try:
            body = await self._get(
                "/email-finder",
                {
                    "domain": domain,
                    "first_name": first_name,
                    "last_name": last_name,
                },
            )
        except HunterAuthError:
            raise
        except HunterError as e:
            if e.status_code == 404:
                # A definitive "no email exists" — cache it so a re-upload of the
                # same sheet does not pay to learn the same thing again.
                empty = {"data": {"email": None}}
                cache_put(db, key, ENDPOINT_EMAIL_FINDER, empty, self.cache_ttl_days)
                return HunterResult(status="not_found", credits_used=1, raw=empty)
            return HunterResult(
                status="error", error_detail=e.message, credits_used=0
            )

        cache_put(db, key, ENDPOINT_EMAIL_FINDER, body, self.cache_ttl_days)
        result = self._parse_finder(body)
        result.credits_used = 1
        return result

    async def enrich_person(self, db, email: str) -> HunterResult:
        """Combined Enrichment. Adds linkedin/title/seniority for one more credit."""
        key = _cache_key(ENDPOINT_COMBINED, email=email)
        cached = cache_get(db, key)
        if cached is not None:
            result = self._parse_combined(cached)
            result.from_cache = True
            result.credits_used = 0
            return result

        try:
            body = await self._get("/combined/find", {"email": email})
        except HunterAuthError:
            raise
        except HunterError as e:
            if e.status_code == 404:
                empty = {"data": {}}
                cache_put(db, key, ENDPOINT_COMBINED, empty, self.cache_ttl_days)
                return HunterResult(status="not_found", credits_used=1, raw=empty)
            return HunterResult(status="error", error_detail=e.message, credits_used=0)

        cache_put(db, key, ENDPOINT_COMBINED, body, self.cache_ttl_days)
        result = self._parse_combined(body)
        result.credits_used = 1
        return result

    # -- response parsing --------------------------------------------------

    @staticmethod
    def _parse_finder(body: dict) -> HunterResult:
        data = (body or {}).get("data") or {}
        email = data.get("email")
        if not email:
            return HunterResult(status="not_found", raw=body or {})

        verification = data.get("verification") or {}
        sources = data.get("sources")
        return HunterResult(
            status="found",
            email=email,
            score=data.get("score"),
            verification=(
                verification.get("status") if isinstance(verification, dict) else None
            ),
            position=data.get("position"),
            linkedin_url=data.get("linkedin_url") or data.get("linkedin"),
            twitter=data.get("twitter"),
            sources_count=len(sources) if isinstance(sources, list) else None,
            raw=body or {},
        )

    @staticmethod
    def _parse_combined(body: dict) -> HunterResult:
        """Combined Enrichment nests person and company; we want the person bits."""
        data = (body or {}).get("data") or {}
        person = data.get("person") or {}
        if not person:
            return HunterResult(status="not_found", raw=body or {})

        employment = person.get("employment") or {}
        linkedin = (person.get("linkedin") or {}).get("handle")
        twitter = (person.get("twitter") or {}).get("handle")
        return HunterResult(
            status="found",
            position=employment.get("title"),
            seniority=employment.get("seniority"),
            department=employment.get("role"),
            linkedin_url=f"https://www.linkedin.com/{linkedin}" if linkedin else None,
            twitter=twitter,
            raw=body or {},
        )
