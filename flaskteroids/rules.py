import logging

_logger = logging.getLogger(__name__)


def rules(*rules_list):
    def decorator(cls):
        _logger.debug(f'applying rules to {cls.__name__}')
        for apply in rules_list:
            apply(cls)
        return cls
    return decorator
