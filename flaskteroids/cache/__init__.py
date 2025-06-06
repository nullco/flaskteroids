from flaskteroids.cache.factory import get_cache
from flaskteroids.cache.base import MISSING


def value(key: str, ttl=None):
    def wrapper(fn):
        def decorator(*args, **kwargs):
            value = fetch(key)
            if value is not MISSING:
                return value
            value = fn(*args, **kwargs)
            store(key, value, ttl)
            return value
        return decorator
    return wrapper


def store(key: str, value, ttl=None):
    get_cache().store(key, value, ttl)


def fetch(key: str):
    return get_cache().fetch(key)


def increment(key: str, ttl=None):
    return get_cache().increment(key, ttl)
