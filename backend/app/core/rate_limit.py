"""Shared slowapi limiter instance — imported by main.py (to register the
middleware/handler) and by individual routes that need a stricter limit
than the global default (e.g. login, to blunt credential-stuffing).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
