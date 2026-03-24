# Rate Limiting — Implementation Notes

## Current State

Per-IP sliding-window rate limiting is implemented in all three services
via `RateLimiter` in each service's `middleware.py`.

| Service | Limit | Window |
|---------|-------|--------|
| Tracker | 120 req/min | 60s |
| AI      | 60 req/min  | 60s |
| Intake  | 120 req/min | 60s |

When triggered, returns HTTP 429 with `Retry-After` header.

## Localhost Exclusion

`127.0.0.1`, `testclient`, and `unknown` IPs are excluded by design
(line 125 of each `middleware.py`). This prevents rate limiting from
blocking health checks and internal service-to-service calls.

## Cloudflare Tunnel Architecture

All external traffic arrives via Cloudflare Tunnel → cloudflared →
`127.0.0.1:{port}`. Because `request.client.host` sees the local proxy
IP (`127.0.0.1`), the rate limiter never triggers for external clients.

## How to Enable for External Traffic

To rate-limit external clients, the middleware must read the real client
IP from the `X-Forwarded-For` or `CF-Connecting-IP` header injected by
Cloudflare.

### Trust Boundary

**Only trust these headers when the request comes from a known proxy.**
Cloudflare Tunnel's `cloudflared` process runs locally and is trusted.
The `CF-Connecting-IP` header is set by Cloudflare's edge and cannot be
spoofed by end users (Cloudflare strips any client-supplied value).

### Implementation (when needed)

In `RequestIDMiddleware.dispatch()`, replace:

```python
client_ip = request.client.host if request.client else "unknown"
```

With:

```python
client_ip = (
    request.headers.get("cf-connecting-ip")
    or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    or (request.client.host if request.client else "unknown")
)
```

Then remove `127.0.0.1` from the exclusion list, keeping only `testclient`
and `unknown`.

### Verification

After the change, test from a browser or `curl` through the public URL
(`https://cftc.stephenandrews.org`). Send 130+ requests in rapid
succession and confirm HTTP 429 with `Retry-After` header.
