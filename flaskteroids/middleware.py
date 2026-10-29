"""Configuration and composition of standard WSGI middleware."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from flaskteroids._method_override import MethodOverrideMiddleware

__all__ = [
    "MethodOverrideMiddleware",
    "Middleware",
    "MiddlewareConfiguration",
    "MiddlewareStack",
]


@dataclass(frozen=True)
class Middleware:
    """An inspectable middleware factory and its constructor arguments."""

    klass: Callable
    args: tuple = ()
    kwargs: Mapping = field(default_factory=dict)

    def __post_init__(self):
        if not callable(self.klass):
            raise TypeError("Middleware must be a callable WSGI middleware factory.")
        object.__setattr__(self, "args", tuple(self.args))
        object.__setattr__(self, "kwargs", MappingProxyType(dict(self.kwargs)))

    @property
    def name(self):
        factory = self.klass
        if not hasattr(factory, "__qualname__"):
            factory = type(factory)
        return f"{factory.__module__}.{factory.__qualname__}"


@dataclass(frozen=True)
class MiddlewareStack(Sequence):
    """The immutable, callable stack, ordered from outermost to innermost."""

    _entries: tuple[Middleware, ...]
    _app: Callable = field(repr=False)

    def __len__(self):
        return len(self._entries)

    def __getitem__(self, index):
        return self._entries[index]

    def __call__(self, environ, start_response):
        return self._app(environ, start_response)


class MiddlewareConfiguration:
    """Record changes to defaults until the application builds its stack.

    Deletions and moves run after additions, inserts, and swaps.
    Targets are middleware factories, matched by identity. Operations targeting
    one entry select the first match; delete removes every matching entry.
    """

    def __init__(self):
        self._operations = []
        self._final_operations = []
        self._built = False

    def use(self, middleware, *args, **kwargs):
        self._record("use", Middleware(middleware, args, kwargs))

    def unshift(self, middleware, *args, **kwargs):
        self._record("unshift", Middleware(middleware, args, kwargs))

    def insert_before(self, target, middleware, *args, **kwargs):
        self._record("insert_before", target, Middleware(middleware, args, kwargs))

    insert = insert_before

    def insert_after(self, target, middleware, *args, **kwargs):
        self._record("insert_after", target, Middleware(middleware, args, kwargs))

    def swap(self, target, middleware, *args, **kwargs):
        self._record("swap", target, Middleware(middleware, args, kwargs))

    def delete(self, target):
        self._record("delete", target, final=True)

    def move_before(self, target, source):
        self._record("move_before", target, source, final=True)

    move = move_before

    def move_after(self, target, source):
        self._record("move_after", target, source, final=True)

    def _record(self, operation, *args, final=False):
        if self._built:
            raise RuntimeError("Middleware configuration is frozen after startup.")
        operations = self._final_operations if final else self._operations
        operations.append((operation, args))

    def build(self, app, *, defaults=()):
        """Apply configuration and construct each middleware once around app."""
        if self._built:
            raise RuntimeError("Middleware configuration is frozen after startup.")
        entries = list(defaults)
        for operation, args in (*self._operations, *self._final_operations):
            self._apply(entries, operation, *args)
        # Freeze before invoking application-owned constructors as well.
        self._built = True
        for entry in reversed(entries):
            app = entry.klass(app, *entry.args, **entry.kwargs)
            if not callable(app):
                raise TypeError(f"Middleware {entry.name} did not return a callable.")
        return MiddlewareStack(tuple(entries), app)

    @staticmethod
    def _index(entries, target):
        for index, entry in enumerate(entries):
            if entry.klass is target:
                return index
        raise ValueError(f"No such middleware in the stack: {target!r}")

    def _apply(self, entries, operation, target, entry=None):
        if operation == "use":
            entries.append(target)
        elif operation == "unshift":
            entries.insert(0, target)
        elif operation == "delete":
            entries[:] = [item for item in entries if item.klass is not target]
        else:
            index = self._index(entries, target)
            if operation in {"move_before", "move_after"}:
                source_index = self._index(entries, entry)
                if source_index == index:
                    return
                source = entries.pop(source_index)
                index = self._index(entries, target)
                entries.insert(index + (operation == "move_after"), source)
            elif operation == "swap":
                entries[index] = entry
            else:
                entries.insert(index + (operation == "insert_after"), entry)
