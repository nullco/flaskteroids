from flask import render_template
from importlib import import_module


def init(app):
    return Routes(app)


class Routes:

    def __init__(self, app):
        self._app = app

    def root(self, *, to):
        cname, caction = to.split('#')
        self._register_view_func('/', cname, caction)

    def _get_controller_class(self, cname):
        controller_module = import_module(f'app.controllers.{cname}_controller')
        return getattr(controller_module, f'{cname.title()}Controller')

    def _register_view_func(self, path, cname, caction):
        ccls = self._get_controller_class(cname)

        def view_func(*args, **kwargs):
            controller_instance = ccls()
            action = getattr(controller_instance, caction)
            res = action(*args, **kwargs)
            if res:
                return res
            view_template = render_template(f'{cname}/{caction}.html', **controller_instance.__dict__)
            return view_template

        self._app.add_url_rule(path, view_func=view_func, methods=["GET"])
