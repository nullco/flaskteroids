import logging

from flaskteroids.declarations import rules_for

_logger = logging.getLogger(__name__)


def rules(*rules_list):
    def decorator(cls):
        _logger.debug(f"registering rules to {cls.__name__}")
        rules_for(cls).entries.extend(rules_list)
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
    definition = rules_for(cls)
    if definition.bound:
        return
    _logger.debug(f"binding rules to {cls.__name__}")
    for ancestor in [*_get_ancestors(cls), cls]:
        for bind in rules_for(ancestor).entries:
            bind(cls)
    definition.bound = True
