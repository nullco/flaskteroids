from flask import render_template
from importlib import import_module
from flask import current_app


def root(*, to):
    cname, caction = to.split('#')
    controller_module = import_module(f'app.controllers.{cname}_controller')
    controller_class = getattr(controller_module, f'{cname.title()}Controller')

    def view_func(*args, **kwargs):
        controller_instance = controller_class()
        action = getattr(controller_instance, caction)
        res = action(*args, **kwargs)
        if res:
            return res
        view_template = render_template(f'{cname}/{caction}.html', **controller_instance.__dict__)
        return view_template

    current_app.add_url_rule("/", view_func=view_func, methods=["GET"])
