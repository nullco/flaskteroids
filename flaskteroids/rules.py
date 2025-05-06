import logging
from flaskteroids import registry

_logger = logging.getLogger(__name__)


def rules(*rules_list):
    def decorator(cls):
        _logger.debug(f'registering rules to {cls.__name__}')
        classes = reversed([c for c in cls.__mro__ if c is not object and c is not cls])
        ns = registry.get(cls)
        entries = []
        ns['rules'] = {'bound': False, 'entries': entries}
        for c in classes:
            entries.extend(registry.get(c).get('rules', {}).get('entries') or [])
        for r in rules_list:
            entries.append(r)
        return cls
    return decorator


def bind_rules(cls):
    ns = registry.get(cls)
    rules = ns.get('rules')
    if not rules:
        return
    if rules['bound']:
        return
    _logger.debug(f'binding rules to {cls.__name__}')
    for apply in rules['entries']:
        apply(cls)
    rules['bound'] = True
