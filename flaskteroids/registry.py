import logging

_logger = logging.getLogger(__name__)
_registry = {}


def get(namespace):
    if isinstance(namespace, type):
        namespace = _get_namespace(namespace)
    if namespace not in _registry:
        _registry[namespace] = {}
    return _registry[namespace]


def _get_namespace(cls):
    ns = f'{cls.__module__}.{cls.__qualname__}'
    _logger.debug(f'namespace for class {cls}: {ns}')
    return ns
