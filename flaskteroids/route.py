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

    def root(self, *, to, as_='root'):
        self._register_view_func('/', to, as_=as_)

    def get(self, path, *, to, as_=None):
        self._register_view_func(path, to, as_=as_)

    def post(self, path, *, to, as_=None):
        self._register_view_func(path, to, ['POST'], as_=as_)

    def put(self, path, *, to, as_=None):
        self._register_view_func(path, to, ['POST', 'PUT'], as_=as_)

    def delete(self, path, *, to, as_=None):
        self._register_view_func(path, to, ['DELETE'], as_=as_)

    def _get_controller_name(self, cname):
        return f'app.controllers.{cname}_controller.{cname.title()}Controller'

    def _get_controller_class(self, cname):
        if cname.startswith('flaskteroids/'):
            cname = cname.replace('flaskteroids/', '')
            cpath = 'flaskteroids.controllers'
        else:
            cpath = 'app.controllers'
        controller_module = import_module(f'{cpath}.{cname}_controller')
        return getattr(controller_module, f'{cname.title()}Controller')

    def _register_view_func(self, path, to, methods=None, as_=None):
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
        if as_:
            view_func_name = as_
        view_func.__name__ = view_func_name

        self._app.add_url_rule(path, view_func=view_func, methods=methods or ['GET'])
