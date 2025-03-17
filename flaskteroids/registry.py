_registry = {}


def get(namespace):
    if isinstance(namespace, type):
        namespace = _get_namespace(namespace)
    if namespace not in _registry:
        _registry[namespace] = {}
    return _registry[namespace]


def _get_namespace(cls):
    return f'{cls.__module__}.{cls.__qualname__}'
