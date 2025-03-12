def before_action(method_name, *, only=None):
    def setup_rule(controller):
        before_action_ = getattr(controller, method_name)
        if not only:
            assert False, 'Not supported yet'

        for action_name in only:
            action = getattr(controller, action_name)
            setattr(controller, action_name, _chain(before_action_, action))
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
