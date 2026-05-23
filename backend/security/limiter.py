"""Iter80 — S9.5: shared slowapi limiter instance.

server.py initialises `app.state.limiter`, but route modules need a
direct reference for `@limiter.limit("...")` decorators. We instantiate
once here and `server.py` imports + binds it to the app.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address


limiter = Limiter(key_func=get_remote_address, headers_enabled=True)
