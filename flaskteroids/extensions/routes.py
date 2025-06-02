import logging
from flask import request
from importlib import import_module
from flaskteroids import params, str_utils
from flaskteroids.controller import ActionController, init
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.discovery import discover_classes


_logger = logging.getLogger(__name__)


class RoutesExtension:

    def __init__(self, app):
        if app:
            self.init_app(app)

    def init_app(self, app):
        self._app = app
        self._paths = set()
        self._controllers = discover_classes(app.config['CONTROLLERS']['LOCATION'], ActionController)
        self._internal_controllers = discover_classes('flaskteroids.controllers', ActionController)
        routes = import_module(app.config['ROUTES']['LOCATION'])
        routes.register(self)
        if not self.has_path('/'):
            self.root(to='flaskteroids/welcome#show')
        for c in self._controllers.values():
            init(c)

        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["flaskteroids.routes"] = self

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

    def resources(self, name, *, only=None):
        only = only or ['index', 'new', 'create', 'show', 'edit', 'update', 'destroy']
        cfg = {
            'index': (self.get, '/{name}/', '{name}#index'),
            'new': (self.get, '/{name}/new/', '{name}#new'),
            'create': (self.post, '/{name}/', '{name}#create'),
            'show': (self.get, '/{name}/<int:id>/', '{name}#show'),
            'edit': (self.get, '/{name}/<int:id>/edit/', '{name}#edit'),
            'update': (self.put, '/{name}/<int:id>/', '{name}#update'),
            'destroy': (self.delete, '/{name}/<int:id>/', '{name}#destroy'),
        }
        for action in only:
            action_cfg = cfg[action]
            method, path, to = action_cfg
            path = path.format(name=name)
            to = to.format(name=name)
            method(path, to=to)

    def resource(self, name, *, only=None):
        only = only or ['new', 'create', 'show', 'edit', 'update', 'destroy']
        cfg = {
            'new': (self.get, '/{name}/new/', '{name}#new'),
            'create': (self.post, '/{name}/', '{name}#create'),
            'show': (self.get, '/{name}/', '{name}#show'),
            'edit': (self.get, '/{name}/edit/', '{name}#edit'),
            'update': (self.put, '/{name}/', '{name}#update'),
            'destroy': (self.delete, '/{name}/', '{name}#destroy'),
        }
        for action in only:
            action_cfg = cfg[action]
            method, path, to = action_cfg
            path = path.format(name=name)
            to = to.format(name=str_utils.pluralize(name))
            method(path, to=to)

    def has_path(self, path):
        return path in self._paths

    def _get_controller_class(self, controller_name):
        if controller_name.startswith('flaskteroids/'):
            controller_name = controller_name.replace('flaskteroids/', '')
            controllers = self._internal_controllers
        else:
            controllers = self._controllers
        controller_name = f'{str_utils.snake_to_camel(controller_name)}Controller'
        controller = controllers.get(controller_name)
        if not controller:
            raise ProgrammerError(f'Controller not found for <{controller_name}>')
        return controller

    def _register_view_func(self, path, to, methods=None, as_=None):
        cname, caction = to.split('#')
        ccls = self._get_controller_class(cname)
        if not hasattr(ccls, caction):
            return

        self._paths.add(path)

        def view_func(*args, **kwargs):
            controller_instance = ccls()
            action = getattr(controller_instance, caction)
            _logger.debug(f'to={to} view_func(args={args}, kwargs={kwargs}')
            params.update(request.form.to_dict(True))
            params.update(kwargs)  # looks like url template params come here
            params.pop('csrf_token', None)
            return action()

        view_func_name = f"{caction}_{str_utils.singularize(cname)}"
        if as_:
            view_func_name = as_
        view_func.__name__ = view_func_name

        self._app.add_url_rule(path, view_func=view_func, methods=methods or ['GET'])
