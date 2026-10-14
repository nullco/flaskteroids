import time

from flaskteroids.cache.base import MISSING


class InMemoryCache:
    def __init__(self):
        self._cache = {}

    def store(self, key: str, value, ttl=None):
        now = time.time()
        self._cache[key] = (value, now + ttl if ttl else None)

    def fetch(self, key: str):
        now = time.time()
        cached = self._cache.get(key)
        if cached:
            value, timestamp = cached
            if not timestamp or now <= timestamp:
                return value
        return MISSING

    def increment(self, key: str, ttl=None):
        val = self.fetch(key)
        if val is MISSING:
            val = 0
        val += 1
        self.store(key, val, ttl)
        return val


_standalone = InMemoryCache()


def store(key: str, value, ttl=None):
    _standalone.store(key, value, ttl)


def fetch(key: str):
    return _standalone.fetch(key)


def increment(key: str, ttl=None):
    return _standalone.increment(key, ttl)
