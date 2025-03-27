import logging
from flask import request
from importlib import import_module
from flaskteroids import params, registry


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

    def _get_controller_name(self, cname):
        return f'app.controllers.{cname}_controller.{cname.title()}Controller'

    def _get_controller_class(self, cname):
        controller_module = import_module(f'app.controllers.{cname}_controller')
        return getattr(controller_module, f'{cname.title()}Controller')

    def _register_view_func(self, path, to, methods=None, prefix=''):
        cname, caction = to.split('#')
        ns = registry.get(self._get_controller_name(cname))
        if 'actions' not in ns:
            ns['actions'] = []
        if caction not in ns['actions']:
            ns['actions'].append(caction)

        def view_func(*args, **kwargs):
            ccls = self._get_controller_class(cname)
            controller_instance = ccls()
            action = getattr(controller_instance, f'invoke_{caction}')
            _logger.debug(f'to={to} view_func(args={args}, kwargs={kwargs}')
            params.update(request.form.to_dict(True))
            params.update(kwargs)  # looks like url template params come here
            params.pop('csrf_token', None)
            return action()

        view_func_name = f"{cname}_{caction}"
        if prefix:
            view_func_name = f"{prefix}_{view_func_name}"
        view_func.__name__ = view_func_name

        self._app.add_url_rule(path, view_func=view_func, methods=methods or ['GET'])
