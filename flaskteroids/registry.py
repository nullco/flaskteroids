_registry = {}


def get(cls):
    namespace = _get_namespace(cls)
    if namespace not in _registry:
        _registry[namespace] = {}
    return _registry[namespace]


def _get_namespace(cls):
    return f'{cls.__module__}.{cls.__qualname__}'
