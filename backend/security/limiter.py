"""Iter80 — S9.5: shared slowapi limiter instance.

server.py initialises `app.state.limiter`, but route modules need a
direct reference for `@limiter.limit("...")` decorators. We instantiate
once here and `server.py` imports + binds it to the app.

Uses a custom key function that prefers X-Forwarded-For (set by our
Kubernetes ingress) so the actual client IP is rate-limited, not the
ingress proxy IP. Falls back to the direct TCP peer otherwise.
"""
from slowapi import Limiter
from starlette.requests import Request


def _client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        # First entry is the original client; trim whitespace.
        return fwd.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "anon"


limiter = Limiter(key_func=_client_key, headers_enabled=False)
