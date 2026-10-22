import logging
from collections.abc import Callable
from functools import wraps
from inspect import CO_OPTIMIZED, currentframe
from types import CodeType, FunctionType
from weakref import WeakSet

from flaskteroids.declarations import RuleDefinition, rules_for
from flaskteroids.exceptions import ProgrammerError

_logger = logging.getLogger(__name__)


# A static allowlist of factory code, not an ambient class-definition context.
_factories: WeakSet[CodeType] = WeakSet()


def declaration[**P, R](factory: Callable[P, R]) -> Callable[P, R]:
    """Record a factory's binding callable in the class where it is declared.

    Factories may compose other declarations, but ordinary function, module,
    and comprehension scopes cannot silently discard a declaration.
    """
    if not isinstance(factory, FunctionType):
        raise TypeError("@declaration requires a Python function.")
    _factories.add(factory.__code__)

    @wraps(factory)
    def record(*args: P.args, **kwargs: P.kwargs) -> R:
        frame = currentframe()
        caller = None
        try:
            if frame is None or frame.f_back is None:
                raise ProgrammerError(
                    "Class-body declarations require Python frame support."
                )
            caller = frame.f_back
            namespace = caller.f_locals
            in_class = (
                caller.f_code.co_name != "<module>"
                and not caller.f_code.co_flags & CO_OPTIMIZED
                and "__module__" in namespace
                and "__qualname__" in namespace
                # Inlined comprehensions expose copies/proxies, not the class mapping.
                and namespace is caller.f_locals
            )
            if not in_class and caller.f_code not in _factories:
                raise ProgrammerError(
                    f"{factory.__name__}() must be called directly in a class body "
                    "or from a @declaration factory."
                )
        finally:
            del caller, frame

        entry = factory(*args, **kwargs)
        if not callable(entry):
            raise ProgrammerError(
                f"Declaration {factory.__name__}() must return a binding callable."
            )
        if in_class:
            name = "_flaskteroids_rules"
            if name not in namespace:
                namespace[name] = RuleDefinition()
            definition = namespace[name]
            if not isinstance(definition, RuleDefinition) or definition.bound:
                raise ProgrammerError(f"{name} is reserved declaration state.")
            definition.entries.append(entry)
        return entry

    return record


def _get_ancestors(cls):
    seen = set()
    result = []

    def visit(c):
        if c in seen or c is object:
            return
        seen.add(c)
        for base in c.__bases__:
            visit(base)
        if c is not cls:
            result.append(c)

    visit(cls)
    return result


def bind_rules(cls):
    definition = rules_for(cls)
    if definition.bound:
        return
    _logger.debug(f"binding rules to {cls.__name__}")
    for ancestor in [*_get_ancestors(cls), cls]:
        for bind in rules_for(ancestor).entries:
            bind(cls)
    definition.bound = True
