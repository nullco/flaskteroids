import re
import logging
from flask import abort, request
from importlib import import_module
from flaskteroids import params
from flaskteroids.inflector import inflector
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
        self._view_functions = {}
        self._controllers = discover_classes(app.config['CONTROLLERS']['LOCATION'], ActionController)
        self._internal_controllers = discover_classes('flaskteroids.controllers', ActionController)
        routes = import_module(app.config['ROUTES']['LOCATION'])
        routes.register(self)
        if not self.has_path('/'):
            self.root(to='flaskteroids/welcome#show')
        self._register_method_overrides()
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
        self._register_view_func(path, to, ['PUT'], as_=as_)

    def delete(self, path, *, to, as_=None):
        self._register_view_func(path, to, ['DELETE'], as_=as_)

    def resources(self, name, *, param=None, only=None, nested=None):
        resources = _ResourceBuilder().resources(name, param=param, only=only, nested=nested)
        for method_name, path, to, as_ in resources:
            method = getattr(self, method_name)
            method(path, to=to, as_=as_)

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
            to = to.format(name=inflector.pluralize(name))
            method(path, to=to)

    def has_path(self, path):
        return path in self._paths

    def _get_controller_class(self, controller_name):
        if controller_name.startswith('flaskteroids/'):
            controller_name = controller_name.replace('flaskteroids/', '')
            controllers = self._internal_controllers
        else:
            controllers = self._controllers
        controller_name = f'{inflector.camelize(controller_name)}Controller'
        return controllers.get(controller_name)

    def _register_view_func(self, path, to, methods=None, as_=None):
        methods = methods or ['GET']
        cname, caction = to.split('#')
        ccls = self._get_controller_class(cname)

        def view_func(*args, **kwargs):
            if not ccls:
                raise ProgrammerError(f'Controller not found for <{cname}>')
            if not hasattr(ccls, caction):
                return

            _logger.debug(f'to={to} view_func(args={args}, kwargs={kwargs}')
            controller_instance = ccls()
            action = getattr(controller_instance, caction)
            flat_params = {}
            flat_params.update(request.form.to_dict(False))
            flat_params.update(kwargs)  # looks like url template params come here
            flat_params.update(request.args.to_dict(False))
            flat_params.pop('csrf_token', None)
            flat_params.pop('_method', None)
            params.update(_unflatten_params(flat_params))
            return action()

        view_func_name = f"{caction}_{inflector.singularize(cname)}"
        if as_:
            view_func_name = as_
        view_func.__name__ = view_func_name

        self._paths.add(path)
        self._view_functions.update({(method, path): view_func for method in methods})
        self._app.add_url_rule(path, view_func=view_func, methods=methods)

    def _register_method_overrides(self):
        path_methods = {}
        for (method, path) in self._view_functions:
            path_methods.setdefault(path, set()).add(method)

        for path, methods in path_methods.items():
            if methods.difference({'GET', 'POST'}):
                self._app.add_url_rule(path, view_func=self._build_override_method(path), methods=['POST'])

    def _build_override_method(self, path):
        def override_method(*args, **kwargs):
            method_override = request.form.get('_method') or request.method
            method_override = method_override.upper()
            if method_override != request.method:
                _logger.debug(f'method override detected: {(method_override, path)}')
            view_func = self._view_functions.get((method_override, path))
            if not view_func:
                abort(405)
            return view_func(*args, **kwargs)
        override_method.__name__ = f'override {path}'
        return override_method


class _ResourceBuilder:

    def __init__(self, path=None):
        self._path = path or ''
        if self._path.endswith('/'):
            self._path = self._path.rstrip('/')

    def resources(self, name, *, param=None, only=None, nested=None):
        only = only or ['index', 'new', 'create', 'show', 'edit', 'update', 'destroy']
        singular = inflector.singularize(name)
        cfg = {
            'index': ('get', '/{name}/', '{name}#index', f'index_{singular}'),
            'new': ('get', '/{name}/new/', '{name}#new', f'new_{singular}'),
            'create': ('post', '/{name}/', '{name}#create', f'create_{singular}'),
            'show': ('get', '/{name}/<{param}>/', '{name}#show', f'show_{singular}'),
            'edit': ('get', '/{name}/<{param}>/edit/', '{name}#edit', f'edit_{singular}'),
            'update': ('put', '/{name}/<{param}>/', '{name}#update', f'update_{singular}'),
            'destroy': ('delete', '/{name}/<{param}>/', '{name}#destroy', f'destroy_{singular}'),
        }
        resources = []
        nested_resources = []
        if nested:
            param = param or f'int:{inflector.singularize(name)}_id'
            nested_resources = nested(_ResourceBuilder(f'{self._path}/{name}/{param}'))
        else:
            param = param or 'int:id'
        for action in only:
            action_cfg = cfg[action]
            method, path, to, as_ = action_cfg
            path = f'{self._path}{path.format(name=name, param=param)}'
            to = to.format(name=name)
            resources.append((method, path, to, as_))
            if action in ('index', 'create', 'show', 'update', 'destroy'):
                resources.append((method, f'{path.rstrip("/")}.json/', to, f'{as_}.json'))
        if nested_resources:
            resources.extend(nested_resources)
        return resources


def _unflatten_params(flat_dict):

    def insert(container, keys, value):
        key = keys[0]
        is_last = len(keys) == 1

        if key == '':
            if not isinstance(container, list):
                container = []
            if is_last:
                container.append(value)
            else:
                if len(container) == 0 or not isinstance(container[-1], (dict, list)):
                    container.append({})
                container[-1] = insert(container[-1], keys[1:], value)
            return container

        if isinstance(container, list):
            index = int(key)
            while len(container) <= index:
                container.append({})
            if is_last:
                container[index] = value
            else:
                container[index] = insert(container[index], keys[1:], value)
            return container

        if is_last:
            container[key] = value
        else:
            if key not in container or not isinstance(container[key], (dict, list)):
                next_key = keys[1]
                container[key] = [] if next_key == '' or re.fullmatch(r'\d+', next_key) else {}
            container[key] = insert(container[key], keys[1:], value)

        return container

    result = {}

    for flat_key, value in flat_dict.items():
        if isinstance(value, list):
            value = value[-1]
        parts = re.findall(r'\w+|\[\]', flat_key.replace(']', ''))
        keys = [parts[0]] + [part if part != '[]' else '' for part in parts[1:]]

        result = insert(result, keys, value)

    return result
