import re
from dataclasses import dataclass
from importlib import import_module

from flask import request
from werkzeug.exceptions import BadRequest, HTTPException

from flaskteroids import params
from flaskteroids._method_override import FORM_PAIRS
from flaskteroids._routing import RouteDescription, collection_route_key
from flaskteroids.controller import ActionController, init
from flaskteroids.discovery import discover_classes
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.inflector import inflector
from flaskteroids.routes import RouteHelper

_PARAMETER = re.compile(r"<(?:(?:[^>]+):)?([^:>]+)>")
_ACTIONS = {
    "index": ("GET", ""),
    "new": ("GET", "/new"),
    "create": ("POST", ""),
    "show": ("GET", None),
    "edit": ("GET", "/edit"),
    "update": (("PUT", "PATCH"), None),
    "destroy": ("DELETE", None),
}


class RoutesExtension:
    def __init__(self, app):
        if app:
            self.init_app(app)

    def init_app(self, app):
        if getattr(self, "_app", app) is not app:
            raise ProgrammerError(
                "A routes extension cannot be shared between applications."
            )
        if "flaskteroids.routes" in app.extensions:
            return
        self._app = app
        self._paths = set()
        self._endpoints = set()
        self._targets = {}
        self._helpers = {}
        self._controllers = discover_classes(
            app.config.paths.controllers, ActionController
        )
        self._internal_controllers = discover_classes(
            "flaskteroids.controllers", ActionController
        )
        app.extensions["flaskteroids.routes"] = self
        import_module(app.config.paths.routes).register(self)
        if not self.has_path("/"):
            self.root(to="flaskteroids/welcome#show")
        for controller in [
            *self._controllers.values(),
            *self._internal_controllers.values(),
        ]:
            init(controller)

    @property
    def helpers(self):
        return self._helpers

    def root(self, *, to, as_="root"):
        self.get("/", to=to, as_=as_)

    def get(self, path, *, to, as_=None):
        self._register_view_func(path, to, ["GET"], as_=as_)

    def post(self, path, *, to, as_=None):
        self._register_view_func(path, to, ["POST"], as_=as_)

    def put(self, path, *, to, as_=None):
        self._register_view_func(path, to, ["PUT"], as_=as_)

    def patch(self, path, *, to, as_=None):
        self._register_view_func(path, to, ["PATCH"], as_=as_)

    def delete(self, path, *, to, as_=None):
        self._register_view_func(path, to, ["DELETE"], as_=as_)

    def resources(self, name, *, param=None, only=None, nested=None):
        self._register_resources(
            _ResourceBuilder().resources(name, param=param, only=only, nested=nested)
        )

    def resource(self, name, *, only=None):
        self._register_resources(_ResourceBuilder().resource(name, only=only))

    def _register_resources(self, resources):
        for resource in resources:
            self._register_view_func(
                resource.path,
                resource.to,
                resource.methods,
                endpoint=resource.endpoint,
                strict_slashes=False,
            )
            json_endpoint = resource.endpoint + ".json"
            self._register_view_func(
                resource.path + ".json",
                resource.to,
                resource.methods,
                endpoint=json_endpoint,
                strict_slashes=False,
            )
            self._register_helper(
                resource.helper,
                RouteDescription(
                    resource.endpoint,
                    tuple(_PARAMETER.findall(resource.path)),
                    resource.path,
                    json_endpoint,
                ),
            )

    def _register_helper(self, name, description):
        existing = self._helpers.get(name)
        if existing is not None:
            if (existing.path, existing.parameters) != (
                description.path,
                description.parameters,
            ):
                raise ProgrammerError(f"Conflicting route helper <{name}>.")
            return
        for suffix in ("_path", "_url"):
            helper_name = name + suffix
            if helper_name in self._app.jinja_env.globals:
                raise ProgrammerError(
                    f"Route helper <{helper_name}> shadows a template global."
                )
            self._app.jinja_env.globals[helper_name] = RouteHelper(helper_name)
        self._helpers[name] = description

    def has_path(self, path):
        return path in self._paths

    def owns_method_miss(self, adapter, error):
        """Classify only method misses; successful requests are never pre-matched."""
        for candidate in error.valid_methods or ():
            try:
                rule, _ = adapter.match(method=candidate, return_rule=True)
            except HTTPException:
                continue
            if rule.endpoint in self._endpoints:
                return True
        return False

    def _get_controller_class(self, controller_name):
        if controller_name.startswith("flaskteroids/"):
            controller_name = controller_name.removeprefix("flaskteroids/")
            controllers = self._internal_controllers
        else:
            controllers = self._controllers
        return controllers.get(f"{inflector.camelize(controller_name)}Controller")

    def _register_view_func(
        self, path, to, methods, as_=None, *, endpoint=None, strict_slashes=None
    ):
        cname, caction = to.split("#")
        controller = self._get_controller_class(cname)

        def view_func(**kwargs):
            if not controller:
                raise ProgrammerError(f"Controller not found for <{cname}>")
            if not hasattr(controller, caction):
                raise ProgrammerError(f"Action not found for <{to}>")
            instance = controller()
            pairs = request.environ.get(FORM_PAIRS)
            if pairs is None:
                pairs = [
                    *request.form.items(multi=True),
                    *request.files.items(multi=True),
                ]
            values = _unflatten_params(pairs)
            values.update(_unflatten_params(request.args.to_dict(False)))
            values.update(kwargs)
            values.pop("csrf_token", None)
            params.update(values)
            return getattr(instance, caction)()

        explicit_endpoint = endpoint is not None or as_ is not None
        endpoint = endpoint or as_ or f"{caction}_{inflector.singularize(cname)}"
        if endpoint in self._app.view_functions:
            if explicit_endpoint or self._targets.get(endpoint) != to:
                raise ProgrammerError(f"Conflicting route endpoint <{endpoint}>.")
            for rule in self._app.url_map.iter_rules(endpoint):
                if rule.rule == path and set(methods).intersection(rule.methods):
                    raise ProgrammerError(f"Conflicting route endpoint <{endpoint}>.")
            view_func = self._app.view_functions[endpoint]
        self._app.add_url_rule(
            path,
            endpoint=endpoint,
            view_func=view_func,
            methods=list(methods),
            strict_slashes=strict_slashes,
            provide_automatic_options=False,
        )
        self._paths.add(path)
        self._endpoints.add(endpoint)
        self._targets[endpoint] = to
        if as_:
            self._register_helper(
                as_, RouteDescription(endpoint, tuple(_PARAMETER.findall(path)), path)
            )


@dataclass(frozen=True)
class _ResourceRoute:
    path: str
    to: str
    methods: tuple[str, ...]
    endpoint: str
    helper: str


class _ResourceBuilder:
    def __init__(self, prefix="", scope=()):
        self.prefix = prefix
        self.scope = scope

    def resource(self, name, *, only=None):
        return self._build(name, singular=True, only=only)

    def resources(self, name, *, param=None, only=None, nested=None):
        return self._build(name, param=param, only=only, nested=nested)

    def _build(self, name, *, singular=False, param=None, only=None, nested=None):
        actions = list(_ACTIONS) if only is None else list(only)
        if singular and only is None:
            actions.remove("index")
        if set(actions) - _ACTIONS.keys() or (singular and "index" in actions):
            raise ProgrammerError(f"Unsupported resource actions: {actions!r}")
        singular_name = name if singular else inflector.singularize(name)
        controller_name = inflector.pluralize(name) if singular else name
        member_name = "_".join((*self.scope, singular_name))
        collection_name = "_".join(
            (*self.scope, name if singular else collection_route_key(name))
        )
        parameter = param or "int:id"
        collection_path = f"{self.prefix}/{name}"
        member_path = (
            collection_path if singular else f"{collection_path}/<{parameter}>"
        )
        resources = []
        for action in actions:
            methods, suffix = _ACTIONS[action]
            methods = (methods,) if isinstance(methods, str) else methods
            if action in {"index", "create"}:
                path, helper = collection_path, collection_name
            elif action == "new":
                path, helper = collection_path + suffix, f"new_{member_name}"
            elif action == "edit":
                path, helper = member_path + suffix, f"edit_{member_name}"
            else:
                path, helper = member_path, member_name
            resources.append(
                _ResourceRoute(
                    path,
                    f"{controller_name}#{action}",
                    methods,
                    f"{action}_{member_name}",
                    helper,
                )
            )
        if nested:
            converter, separator, member_parameter = parameter.rpartition(":")
            ancestor_parameter = f"{singular_name}_{member_parameter}"
            ancestor = (
                f"{converter}:{ancestor_parameter}" if separator else ancestor_parameter
            )
            child = _ResourceBuilder(
                f"{collection_path}/<{ancestor}>", (*self.scope, singular_name)
            )
            resources.extend(nested(child) or ())
        return resources


def _unflatten_params(flat_dict):
    def insert(container, keys, value, *, indexed):
        key = keys[0]
        is_last = len(keys) == 1
        if key == "":
            if not isinstance(container, list):
                raise BadRequest("Conflicting parameter shapes.")
            if is_last:
                container.append(value)
            else:
                if len(container) == 0 or not isinstance(container[-1], (dict, list)):
                    container.append({})
                container[-1] = insert(container[-1], keys[1:], value, indexed=indexed)
            return container
        if isinstance(container, list):
            if not indexed or not key.isdecimal():
                raise BadRequest("Conflicting parameter shapes.")
            index = int(key)
            while len(container) <= index:
                container.append({})
            if is_last:
                container[index] = value
            else:
                container[index] = insert(
                    container[index], keys[1:], value, indexed=indexed
                )
            return container
        if is_last:
            container[key] = value
        else:
            if key not in container or container[key] is None:
                next_key = keys[1]
                container[key] = (
                    []
                    if next_key == "" or (indexed and re.fullmatch(r"\d+", next_key))
                    else {}
                )
            elif not isinstance(container[key], (dict, list)):
                raise BadRequest("Conflicting parameter shapes.")
            container[key] = insert(container[key], keys[1:], value, indexed=indexed)
        return container

    result = {}
    entries = flat_dict.items() if isinstance(flat_dict, dict) else flat_dict
    for flat_key, value in entries:
        parts = re.findall(r"\w+|\[\]", flat_key)
        if not parts:
            continue
        keys = [parts[0]] + [part if part != "[]" else "" for part in parts[1:]]
        if isinstance(value, list):
            values = value if keys[-1] == "" else value[-1:]
        else:
            values = [value]
        for entry in values:
            result = insert(result, keys, entry, indexed=keys[0] != "_method")
    return result
