"""Application-local helper discovery and render-scoped view contexts."""

import inspect
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path

from flask import current_app, g, has_request_context

from flaskteroids._view_helpers import (
    HelperMethod,
    IncludeHelpers,
    active_view,
    render_assigns,
    render_scope,
)
from flaskteroids.controller import Controller
from flaskteroids.declarations import rules_for
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.inflector import inflector
from flaskteroids.mailer import ActionMailer
from flaskteroids.rules import _get_ancestors
from flaskteroids.turbo import TurboStreamBuilder
from flaskteroids.turbo.rendering import render


def _discover(package_name):
    parts = package_name.split(".")
    for length in range(1, len(parts) + 1):
        name = ".".join(parts[:length])
        if find_spec(name) is None:
            return {}
        import_module(name)
    package = import_module(package_name)
    if not hasattr(package, "__path__"):
        raise ProgrammerError("config.paths.helpers must name a package")

    names = set()
    for root in package.__path__:
        for path in Path(root).rglob("*_helper.py"):
            relative = path.relative_to(root).with_suffix("")
            if not any(part.startswith("_") for part in relative.parts):
                names.add(relative.as_posix())

    found = {}
    for name in sorted(names):
        module = import_module(f"{package_name}.{name.replace('/', '.')}")
        class_name = inflector.camelize(name.rsplit("/", 1)[-1])
        cls = vars(module).get(class_name)
        if not isinstance(cls, type) or cls.__module__ != module.__name__:
            raise ProgrammerError(
                f"Helper module <{module.__name__}> must define {class_name}"
            )
        found[name.removesuffix("_helper")] = cls
    return found


def _delegate(method_name):
    def call(self, *args, **kwargs):
        return getattr(self._flaskteroids_owner, method_name)(*args, **kwargs)

    return call


class _ViewContext:
    def __init__(self, app, scope, owner, assigns):
        self._flaskteroids_app = app
        self._flaskteroids_scope = scope
        self._flaskteroids_owner = owner
        self._flaskteroids_assigns = assigns

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._flaskteroids_assigns:
            return self._flaskteroids_assigns[name]
        if (
            name == "params"
            and self._flaskteroids_scope[0] == "controller"
            and self._flaskteroids_owner is not None
        ):
            return self._flaskteroids_owner.params
        globals_ = self._flaskteroids_app.jinja_env.globals
        if name in globals_:
            return globals_[name]
        raise AttributeError(name)

    def _flaskteroids_exports(self):
        return {
            name: getattr(self, name)
            for name, member in inspect.getmembers(type(self))
            if not name.startswith("_")
            and (inspect.isfunction(member) or inspect.ismethod(member))
        }

    @property
    def turbo_stream(self):
        return TurboStreamBuilder(renderer=self.render)

    def render(self, template=None, **kwargs):
        token = active_view.set(self)
        try:
            return render(template, **kwargs)
        finally:
            active_view.reset(token)


class HelpersExtension:
    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        if vars(self).get("_app", app) is not app:
            raise ProgrammerError(
                "A helpers extension cannot be shared between applications."
            )
        if "flaskteroids.helpers" in app.extensions:
            return
        self._app = app
        self._helpers = _discover(app.config.paths.helpers)
        self._contexts = {}
        self._mailers = {}
        app.extensions["flaskteroids.helpers"] = self

    def register_mailer(self, cls):
        key = f"{cls.__module__}:{cls.__qualname__}"
        self._mailers[key] = cls
        self._context_class(cls, "mailer")
        return key

    def restore_mailer(self, key, assigns):
        if key is None:
            return None
        try:
            cls = self._mailers[key]
        except KeyError as error:
            raise ProgrammerError(
                f"Mailer helper owner not registered: {key}"
            ) from error
        owner = object.__new__(cls)
        vars(owner).update(assigns)
        return owner

    def validate_controller(self, cls):
        self._context_class(cls, "controller")

    def _resolve(self, spec):
        if isinstance(spec, type):
            return [spec]
        if spec == "all":
            return list(self._helpers.values())
        key = "/".join(
            inflector.underscore(part.removesuffix("Helper"))
            for part in spec.replace(".", "/").split("/")
        )
        try:
            return [self._helpers[key]]
        except KeyError as error:
            raise ProgrammerError(f"Helper not found for <{spec}>") from error

    def _conventional_name(self, cls, kind):
        package = (
            self._app.config.paths.controllers
            if kind == "controller"
            else self._app.config.paths.mailers
        )
        suffix = "Controller" if kind == "controller" else ""
        name = inflector.underscore(cls.__name__.removesuffix(suffix))
        if cls.__module__.startswith(package + "."):
            relative = cls.__module__[len(package) + 1 :].replace(".", "/")
            module_name = (
                relative.removesuffix("_controller")
                if kind == "controller"
                else relative
            )
            if module_name.rsplit("/", 1)[-1] == name:
                return module_name
        return name

    def _context_class(self, owner_class, kind):
        include_all = (
            kind == "controller"
            and self._app.config.action_controller.include_all_helpers
        )
        cache_key = (owner_class, kind, include_all)
        if cache_key in self._contexts:
            return self._contexts[cache_key]
        base = _ViewContext

        def include(cls):
            nonlocal base
            if any(
                "__init__" in vars(ancestor)
                for ancestor in cls.__mro__
                if ancestor is not object
            ):
                raise ProgrammerError(
                    f"Helper mixin <{cls.__name__}> cannot define __init__"
                )
            if not issubclass(base, cls):
                try:
                    base = type("_Helpers", (cls, base), {})
                except TypeError as error:
                    raise ProgrammerError(
                        f"Incompatible helper mixin <{cls.__name__}>"
                    ) from error

        if kind == "controller":
            if "application" in self._helpers:
                include(self._helpers["application"])
            if include_all and owner_class is None:
                for cls in self._helpers.values():
                    include(cls)

        if owner_class is not None:
            owner_base = Controller if kind == "controller" else ActionMailer
            pending_rules = []
            first_owner = True
            for ancestor in [*_get_ancestors(owner_class), owner_class]:
                if ancestor is owner_base:
                    continue
                pending_rules.extend(rules_for(ancestor).entries)
                if not issubclass(ancestor, owner_base):
                    continue
                conventional = self._conventional_name(ancestor, kind)
                if conventional in self._helpers:
                    include(self._helpers[conventional])
                if first_owner and include_all:
                    for cls in self._helpers.values():
                        include(cls)
                first_owner = False
                methods = {}
                for rule in pending_rules:
                    if isinstance(rule, IncludeHelpers):
                        for spec in rule.helpers:
                            for cls in self._resolve(spec):
                                include(cls)
                    elif isinstance(rule, HelperMethod):
                        methods[rule.name] = _delegate(rule.method_name)
                pending_rules.clear()
                if methods:
                    base = type("_OwnerHelpers", (base,), methods)

        # Helper classes are mixins, not separately constructed service objects.
        context_class = type("_View", (base,), {"__init__": _ViewContext.__init__})
        self._contexts[cache_key] = context_class
        return context_class

    def template_context(self):
        scope = render_scope.get()
        if scope is None:
            owner = getattr(g, "controller", None) if has_request_context() else None
            scope = ("controller", id(owner) if owner is not None else None)
            owner_class = type(owner) if owner is not None else None
            assigns = vars(owner) if owner is not None else {}
        else:
            kind, owner = scope
            scope = (kind, id(owner) if owner is not None else None)
            owner_class = type(owner) if owner is not None else None
            assigns = render_assigns.get() or {}
        view = active_view.get()
        if (
            view is None
            or view._flaskteroids_app is not current_app._get_current_object()
            or view._flaskteroids_scope != scope
        ):
            view = self._context_class(owner_class, scope[0])(
                self._app, scope, owner, assigns
            )
        context = view._flaskteroids_exports()
        context["turbo_stream"] = view.turbo_stream
        if scope[0] == "controller" and owner is not None:
            context["params"] = owner.params
        return context
