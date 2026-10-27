from http import HTTPStatus

from flask import abort, request

from flaskteroids import cache
from flaskteroids.actions import before_action
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.rules import declaration


def _keygen():
    return request.remote_addr


def _default_handler():
    abort(HTTPStatus.TOO_MANY_REQUESTS)


@declaration
def rate_limit(*, to, within=None, only=None, by=None, using=None):
    callback = before_action("_rate_limit", only=only)

    def bind(cls):
        if isinstance(using, str) and not callable(getattr(cls, using, None)):
            raise ProgrammerError("rate_limit() requires a callable handler method.")

        def _rate_limit(self):
            rate_limit_handler = (
                getattr(self, using)
                if isinstance(using, str)
                else using or _default_handler
            )
            keygen = by or _keygen
            key = f"rate-limit:{keygen()}"
            count = cache.increment(key, within)
            if count > to:
                return rate_limit_handler()

        cls._rate_limit = _rate_limit
        callback(cls)

    return bind
