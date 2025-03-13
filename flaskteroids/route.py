import logging
from flask import request
from flask import render_template
from importlib import import_module
from flaskteroids import params
from flaskteroids.exceptions import Redirect


_logger = logging.getLogger(__name__)


def init(app):
    return Routes(app)


class Routes:

    def __init__(self, app):
        self._app = app

    def root(self, *, to):
        self._register_view_func('/', to, prefix='root')

    def get(self, path, *, to):
        self._register_view_func(path, to)

    def post(self, path, *, to):
        self._register_view_func(path, to, ['POST'])

    def put(self, path, *, to):
        self._register_view_func(path, to, ['POST', 'PUT'])

    def delete(self, path, *, to):
        self._register_view_func(path, to, ['DELETE'])

    def _get_controller_class(self, cname):
        controller_module = import_module(f'app.controllers.{cname}_controller')
        return getattr(controller_module, f'{cname.title()}Controller')

    def _register_view_func(self, path, to, methods=None, prefix=''):
        cname, caction = to.split('#')
        ccls = self._get_controller_class(cname)

        def view_func(*args, **kwargs):
            controller_instance = ccls()
            action = getattr(controller_instance, caction)
            _logger.debug(f'to={to} view_func(args={args}, kwargs={kwargs}')
            params.update(request.form.to_dict(True))
            params.update(kwargs)  # looks like url template params come here
            try:
                res = action()
                if res:
                    return res
                view_template = render_template(f'{cname}/{caction}.html', **controller_instance.__dict__)
                return view_template
            except Redirect as r:
                return r.response

        view_func_name = f"{cname}_{caction}"
        if prefix:
            view_func_name = f"{prefix}_{view_func_name}"
        view_func.__name__ = view_func_name

        self._app.add_url_rule(path, view_func=view_func, methods=methods or ['GET'])
