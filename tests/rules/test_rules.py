import inspect
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest

import tests.rules.fixtures as declarations
from flaskteroids import declaration
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.rules import bind_rules
from tests.rules.fixtures import record, record_pair
from tests.rules.fixtures import record as record_alias


def test_declarations_preserve_import_resolution_and_call_order():
    events = []

    class Example:
        record("direct", into=events)
        record_alias("alias", into=events)
        declarations.record("qualified", into=events)
        record("repeat", into=events)

    assert events == []
    bind_rules(Example)
    assert events == ["direct", "alias", "qualified", "repeat"]


def test_declarations_combine_ancestors_once_and_keep_siblings_independent():
    events = []

    class Root:
        record("root", into=events)

    class Left(Root):
        record("left", into=events)

    class Right(Root):
        record("right", into=events)

    class Child(Left, Right):
        record("child", into=events)

    class Sibling(Root):
        record("sibling", into=events)

    bind_rules(Child)
    bind_rules(Child)
    assert events == ["root", "left", "right", "child"]
    events.clear()
    bind_rules(Sibling)
    assert events == ["root", "sibling"]
    events.clear()
    bind_rules(Root)
    assert events == ["root"]


def test_declarations_keep_nested_class_scopes_independent():
    events = []

    class Outer:
        record("outer-first", into=events)

        class Inner:
            record("inner", into=events)

        record("outer-last", into=events)

    bind_rules(Outer)
    assert events == ["outer-first", "outer-last"]
    events.clear()
    bind_rules(Outer.Inner)
    assert events == ["inner"]


def test_declarations_preserve_unrelated_local_functions():
    events = []

    def record(value):
        events.append(value)

    class Example:
        record("ordinary")

    bind_rules(Example)
    assert events == ["ordinary"]


def test_declarations_support_class_body_loops():
    events = []

    class Example:
        for value in ["first", "second"]:
            record(value, into=events)

    bind_rules(Example)
    assert events == ["first", "second"]


def test_declarations_preserve_class_docstrings_and_super():
    events = []

    class Parent:
        def greeting(self):
            return "parent"

    class Child(Parent):
        """A normal Python class."""

        record("child", into=events)

        def greeting(self):
            return super().greeting() + "-child"

    bind_rules(Child)
    assert Child.__doc__ == "A normal Python class."
    assert Child().greeting() == "parent-child"
    assert events == ["child"]


def test_declarations_work_with_abstract_mixins_and_custom_metaclasses():
    events = []

    class Contract(ABC):
        record("abstract", into=events)

        @abstractmethod
        def work(self):
            pass

    class CustomMeta(type(Contract)):
        def __new__(mcls, name, bases, namespace, **kwargs):
            return super().__new__(mcls, name, bases, dict(namespace), **kwargs)

    class Concrete(Contract, metaclass=CustomMeta):
        record("concrete", into=events)

        def work(self):
            return "done"

    bind_rules(Concrete)
    assert Concrete().work() == "done"
    assert events == ["abstract", "concrete"]


def test_declaration_factories_compose_without_registering_inner_calls_twice():
    events = []

    class Example:
        record_pair("first", "second", into=events)

    bind_rules(Example)
    assert events == ["first", "second"]


def test_declarations_preserve_factory_signatures():
    signature = inspect.signature(record)
    assert list(signature.parameters) == ["value", "into"]
    assert signature.parameters["value"].annotation is str
    assert signature.parameters["into"].kind is inspect.Parameter.KEYWORD_ONLY


@pytest.mark.parametrize(
    "frame",
    [None, SimpleNamespace(f_back=None)],
    ids=["missing-current-frame", "missing-caller-frame"],
)
def test_declarations_report_unavailable_frame_support(monkeypatch, frame):
    monkeypatch.setattr("flaskteroids.rules.currentframe", lambda: frame)
    with pytest.raises(ProgrammerError, match="frame support"):

        class Example:
            record("unavailable", into=[])


def test_declarations_reject_ordinary_function_scopes():
    with pytest.raises(ProgrammerError, match="class body"):
        record("outside", into=[])


def test_declarations_reject_module_scopes():
    with pytest.raises(ProgrammerError, match="class body"):
        exec("from tests.rules.fixtures import record\nrecord('module', into=[])")


def test_declarations_reject_unmarked_helpers():
    def helper():
        record("discarded", into=[])

    with pytest.raises(ProgrammerError, match="@declaration"):

        class Example:
            helper()


@pytest.mark.parametrize("preceding", [False, True])
def test_declarations_reject_comprehension_scopes(preceding):
    with pytest.raises(ProgrammerError, match="class body"):

        class Example:
            if preceding:
                record("preceding", into=[])
            [record(value, into=[]) for value in ["discarded"]]


def test_declaration_factories_reject_calls_outside_class_bodies():
    with pytest.raises(ProgrammerError, match="class body"):
        record_pair("first", "second", into=[])


def test_declarations_reject_factories_without_binding_callables():
    @declaration
    def broken():
        return None

    with pytest.raises(ProgrammerError, match="binding callable"):

        class Example:
            broken()


def test_declaration_decorator_requires_python_functions():
    with pytest.raises(TypeError, match="Python function"):
        declaration(object())


def test_failed_class_definitions_leave_no_collector_state():
    events = []
    with pytest.raises(RuntimeError):

        class Broken:
            record("discarded", into=events)
            raise RuntimeError("stop")

    class Healthy:
        record("healthy", into=events)

    bind_rules(Healthy)
    assert events == ["healthy"]
    with pytest.raises(ProgrammerError, match="class body"):
        record("outside", into=events)


def test_concurrent_class_bodies_collect_independently():
    barrier = Barrier(2)

    def define(value):
        events = []

        class Example:
            record(value + "-first", into=events)
            barrier.wait(timeout=10)
            record(value + "-second", into=events)

        return Example, events

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(define, ["left", "right"]))
    for cls, _ in results:
        bind_rules(cls)
    assert [events for _, events in results] == [
        ["left-first", "left-second"],
        ["right-first", "right-second"],
    ]
