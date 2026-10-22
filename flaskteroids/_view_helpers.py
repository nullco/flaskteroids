"""Helper declarations and render-local scope, without application resources."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from flaskteroids.exceptions import ProgrammerError
from flaskteroids.rules import declaration

# None means ordinary Flask rendering; mailers explicitly select their own scope.
render_scope = ContextVar("flaskteroids.helper_scope", default=None)
active_view = ContextVar("flaskteroids.active_view", default=None)
render_assigns = ContextVar("flaskteroids.helper_assigns", default=None)


@contextmanager
def mailer_scope(owner, assigns):
    token = render_scope.set(("mailer", owner))
    assigns_token = render_assigns.set(assigns)
    try:
        yield
    finally:
        render_assigns.reset(assigns_token)
        render_scope.reset(token)


@dataclass(frozen=True)
class HelperMethod:
    method_name: str
    name: str

    def __call__(self, cls):
        if not callable(getattr(cls, self.method_name)):
            raise ProgrammerError(
                f"Helper method <{self.method_name}> must be callable"
            )


@dataclass(frozen=True)
class IncludeHelpers:
    helpers: tuple[type | str, ...]

    def __call__(self, cls):
        pass


@declaration
def helper_method(method_name: str, *, name: str | None = None):
    """Expose a private controller or mailer method as a template helper."""
    helper_name = name if name is not None else method_name.lstrip("_")
    if not method_name.startswith("_") or method_name.startswith("__"):
        raise ProgrammerError(
            "Helper methods should follow conventions for private methods"
        )
    if not helper_name.isidentifier() or helper_name.startswith("_"):
        raise ProgrammerError("Template helper names must be public identifiers")
    return HelperMethod(method_name, helper_name)


@declaration
def helper(*helpers: type | str):
    """Include helper classes or conventional names in this owner's views."""
    if not helpers or any(
        not isinstance(value, (type, str)) or value == "" for value in helpers
    ):
        raise ProgrammerError("helper() expects helper classes or nonempty names")
    return IncludeHelpers(helpers)
