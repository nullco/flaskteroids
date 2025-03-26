from flaskteroids import registry


def before_action(method_name, *, only=None):
    def setup_rule(controller_cls):
        before_action_ = getattr(controller_cls, method_name)
        actions = only if only else None
        if not actions:
            ns = registry.get(controller_cls)
            actions = ns['actions']

        for action_name in actions:
            action = getattr(controller_cls, action_name)
            setattr(controller_cls, action_name, _chain(before_action_, action))
    return setup_rule


def _chain(*actions):
    def wrapper(*args, **kwargs):
        res = None
        for action in actions:
            res = action(*args, **kwargs)
            if res:
                break
        return res
    return wrapper
