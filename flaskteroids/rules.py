import logging
from flaskteroids import registry

_logger = logging.getLogger(__name__)


def rules(*rules_list):
    def decorator(cls):
        _logger.debug(f'registering rules to {cls.__name__}')
        classes = _get_ancestors(cls)
        ns = registry.get(cls)
        entries = []
        ns['rules'] = {'bound': False, 'entries': entries}
        for c in classes:
            entries.extend(registry.get(c).get('rules', {}).get('entries') or [])
        for r in rules_list:
            entries.append(r)
        return cls
    return decorator


def _get_ancestors(cls):
    seen = set()
    result = []

    def visit(c):
        if c in seen or c is object:
            return
        seen.add(c)
        for base in c.__bases__:
            visit(base)
        if c is not cls:
            result.append(c)

    visit(cls)
    return result


def bind_rules(cls):
    ns = registry.get(cls)
    if 'rules' not in ns:
        # We register an empty set of rules in order to allow rules inheritance
        # even when rules are not present in the current class
        rules()(cls)
    registered_rules = ns.get('rules')
    if not registered_rules:
        return
    if registered_rules['bound']:
        return
    _logger.debug(f'binding rules to {cls.__name__}')
    for bind in registered_rules['entries']:
        bind(cls)
    registered_rules['bound'] = True
