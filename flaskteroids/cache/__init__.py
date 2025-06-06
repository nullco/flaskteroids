from flaskteroids.cache.factory import get_cache
from flaskteroids.cache.base import MISSING


def value(key: str, ttl: int = 60):
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


def store(key: str, value, ttl: int = 60):
    get_cache().store(key, value, ttl)


def fetch(key: str):
    return get_cache().fetch(key)
