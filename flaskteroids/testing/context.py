from contextlib import contextmanager
from contextvars import ContextVar


_current_client = ContextVar("flaskteroids_test_client")
_current_response = ContextVar("flaskteroids_test_response", default=None)


@contextmanager
def activate_test_context(client):
    client_token = _current_client.set(client)
    response_token = _current_response.set(None)
    try:
        yield
    finally:
        _current_response.reset(response_token)
        _current_client.reset(client_token)


def current_response():
    return _current_response.get()


def _request(method, url, *, params=None, **options):
    client = _current_client.get()
    if params is not None:
        options.setdefault("data", _flatten_params(params))
    response = client.open(url, method=method, **options)
    _current_response.set(response)
    return response


def get(url, *, params=None, **options):
    if params:
        options.setdefault("query_string", _flatten_params(params))
    return _request("GET", url, **options)


def post(url, *, params=None, **options):
    return _request("POST", url, params=params, **options)


def patch(url, *, params=None, **options):
    return _request("PATCH", url, params=params, **options)


def put(url, *, params=None, **options):
    return _request("PUT", url, params=params, **options)


def delete(url, *, params=None, **options):
    return _request("DELETE", url, params=params, **options)


def _flatten_params(values, prefix=None):
    flattened = {}
    for key, value in values.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flattened.update(_flatten_params(value, name))
        else:
            flattened[name] = value
    return flattened
