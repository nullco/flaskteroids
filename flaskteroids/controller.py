
def before_action(method_name, *, only=None):
    def setup_rule(controller):
        before_action_method = getattr(controller, method_name)
        if not only:
            assert False, 'Not supported yet'

        for action_name in only:
            action = getattr(controller, action_name)

            def new_action(*args, **kwargs):
                before_action_method(*args, **kwargs)
                action(*args, **kwargs)

            setattr(controller, action_name, new_action)
    return setup_rule
