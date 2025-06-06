import time
from flaskteroids.cache.base import MISSING


_cache = {}


def store(key: str, value, ttl=None):
    now = time.time()
    _cache[key] = (value, now + ttl if ttl else None)


def fetch(key: str):
    now = time.time()
    cached = _cache.get(key)

    if cached:
        value, timestamp = cached
        if not timestamp or now <= timestamp:
            return value
    return MISSING


def increment(key: str, ttl=None):
    val = fetch(key)
    if val is MISSING:
        val = 0
    val += 1
    store(key, val, ttl)
    return val
