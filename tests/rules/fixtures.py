from collections.abc import Callable

from flaskteroids import declaration


@declaration
def record(value: str, *, into: list[str]) -> Callable[[type], None]:
    def bind(cls):
        into.append(value)

    return bind


@declaration
def record_pair(first: str, second: str, *, into: list[str]):
    bindings = record(first, into=into), record(second, into=into)

    def bind(cls):
        for binding in bindings:
            binding(cls)

    return bind
