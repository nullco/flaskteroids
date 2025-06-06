import time
from flaskteroids.cache.base import MISSING


_cache = {}


def store(key: str, value, ttl: int = 60):
    now = time.time()
    _cache[key] = (value, now + ttl)


def fetch(key: str):
    now = time.time()
    cached = _cache.get(key)

    if cached:
        value, timestamp = cached
        if now <= timestamp:
            return value
    return MISSING
