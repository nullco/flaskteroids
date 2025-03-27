from collections import defaultdict
import logging
from flask import render_template
from flaskteroids import registry


_logger = logging.getLogger(__name__)


def before_action(method_name, *, only=None):
    def register(controller_cls):
        actions = only if only else None
        ns = registry.get(controller_cls)

        if 'before_action' not in ns:
            ns['before_action'] = defaultdict(lambda: [])
        if not actions:
            actions = ns['actions'] if 'actions' in ns else []

        for action_name in actions:
            _logger.debug(f'before_action: setting {method_name} before {action_name} on {controller_cls.__name__}')
            ns['before_action'][action_name].append(method_name)
    return register


def _chain(*actions):
    def wrapper(*args, **kwargs):
        res = None
        for action in actions:
            res = action(*args, **kwargs)
            if res:
                break
        return res
    return wrapper


class ActionController:

    def __getattr__(self, name):
        if name.startswith('invoke_'):
            name = name.replace('invoke_', '')

            def wrapper(*args, **kwargs):
                ns = registry.get(self.__class__)
                before_action = [ba for ba in ns.get('before_action', {}).get(name, [])]
                before_action = [getattr(self, ba) for ba in before_action]
                action = _chain(*before_action, getattr(self, name))
                res = action(*args, **kwargs)
                if res:
                    return res
                cname = self.__class__.__name__.replace("Controller", "").lower()
                view_template = render_template(f'{cname}/{name}.html', **self.__dict__)
                return view_template
            return wrapper

        raise AttributeError(f"{self.__class__.__name__} does not have attribute {name}")
