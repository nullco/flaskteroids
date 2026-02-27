_registry = {}


def get(cls) -> dict:
    namespace = _get_namespace(cls)
    if namespace not in _registry:
        _registry[namespace] = {}
    return _registry[namespace]


def _get_namespace(cls):
    # Use class identity to avoid namespace collisions for classes defined
    # multiple times (e.g., nested classes in tests). Qualname alone can be
    # the same across different class objects, which caused shared registry
    # state and flaky tests. Including the object's id ensures a unique
    # namespace per class object.
    ns = f'{cls.__module__}.{cls.__qualname__}.{id(cls)}'
    return ns
