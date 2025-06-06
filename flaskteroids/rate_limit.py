from http import HTTPStatus
from flask import request, abort
from flaskteroids.actions import before_action
from flaskteroids import cache


def _keygen():
    return request.remote_addr


def _with():
    abort(HTTPStatus.TOO_MANY_REQUESTS)


def rate_limit(*, to, within=None, only=None, by=None, with_=None):
    def bind(cls):
        def _rate_limit(self):
            rate_limit_handler = with_ or _with
            keygen = by or _keygen
            key = f'rate-limit:{keygen()}'
            count = cache.increment(key, within)
            if count > to:
                return rate_limit_handler()
        cls._rate_limit = _rate_limit
        before_action('_rate_limit', only=only)(cls)
    return bind
