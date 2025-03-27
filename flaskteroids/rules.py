import logging
from flaskteroids import registry

_logger = logging.getLogger(__name__)


def rules(*rules_list):
    def decorator(cls):
        _logger.debug(f'applying rules to {cls.__name__}')
        classes = reversed([c for c in cls.__mro__ if c is not object and c is not cls])
        ns = registry.get(cls)
        ns['rules'] = []
        for c in classes:
            ns['rules'].extend(registry.get(c).get('rules') or [])
        for r in rules_list:
            ns['rules'].append(r)
        for apply in ns['rules']:
            apply(cls)
        return cls
    return decorator
