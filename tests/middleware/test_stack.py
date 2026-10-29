from contextlib import closing
from dataclasses import FrozenInstanceError

import pytest
from werkzeug.test import EnvironBuilder

from flaskteroids.middleware import Middleware, MiddlewareConfiguration
from tests.middleware.support import EarlyResponse, First, Second, Third


@pytest.fixture
def events():
    return []


@pytest.fixture
def config():
    return MiddlewareConfiguration()


@pytest.fixture
def endpoint(events):
    def dispatch(environ, start_response):
        events.append("dispatch")
        start_response("200 OK", [])
        return [b"hello"]

    return dispatch


def factories(stack):
    return [entry.klass for entry in stack]


def test_use_wraps_in_request_order_and_unwinds_in_reverse(config, endpoint, events):
    config.use(First, events, label="outer")
    config.use(Second, events, label="inner")
    stack = config.build(endpoint)
    assert events == [("build", "inner"), ("build", "outer")]
    events.clear()

    assert stack({}, lambda *args: None) == [b"hello"]
    assert events == [
        ("before", "outer"),
        ("before", "inner"),
        "dispatch",
        ("after", "inner"),
        ("after", "outer"),
    ]


@pytest.mark.parametrize(
    "operation, expected",
    [
        ("insert_before", [First, Third, Second]),
        ("insert_after", [First, Second, Third]),
        ("swap", [First, Third]),
        ("insert", [First, Third, Second]),
    ],
)
def test_relative_operations_customize_defaults(
    config, endpoint, events, operation, expected
):
    getattr(config, operation)(Second, Third, events, label="custom")
    stack = config.build(
        endpoint, defaults=(Middleware(First, (events,)), Middleware(Second, (events,)))
    )
    assert factories(stack) == expected
    custom = next(entry for entry in stack if entry.klass is Third)
    assert custom.args == (events,)
    assert custom.kwargs == {"label": "custom"}


def test_unshift_places_middleware_before_defaults(config, endpoint, events):
    config.unshift(First, events)
    stack = config.build(endpoint, defaults=(Middleware(Second, (events,)),))
    assert factories(stack) == [First, Second]


@pytest.mark.parametrize(
    "operation, target, source, expected",
    [
        ("move_before", First, Third, [Third, First, Second]),
        ("move_after", Third, First, [Second, Third, First]),
        ("move_before", Third, First, [Second, First, Third]),
        ("move_after", First, Third, [First, Third, Second]),
        ("move_before", First, First, [First, Second, Third]),
        ("move_after", First, First, [First, Second, Third]),
        ("move", First, Third, [Third, First, Second]),
    ],
)
def test_moves_preserve_entries_and_constructor_options(
    config, endpoint, events, operation, target, source, expected
):
    getattr(config, operation)(target, source)
    for middleware in (First, Second, Third):
        config.use(middleware, events, label=middleware.__name__)
    stack = config.build(endpoint)
    assert factories(stack) == expected
    assert [entry.kwargs["label"] for entry in stack] == [
        middleware.__name__ for middleware in expected
    ]


def test_delete_applies_after_additions_and_removes_all_matches(
    config, endpoint, events
):
    config.delete(First)
    config.delete(Third)
    config.use(First, events)
    config.use(Second, events)
    config.use(First, events)
    stack = config.build(endpoint)
    assert factories(stack) == [Second]
    assert events == [("build", "Second")]


@pytest.mark.parametrize("operation", ["insert_before", "insert_after", "swap"])
def test_relative_operations_select_first_matching_factory(
    config, endpoint, events, operation
):
    config.use(First, events, label="one")
    config.use(First, events, label="two")
    getattr(config, operation)(First, Second, events)
    stack = config.build(endpoint)
    assert stack[-1].klass is First
    assert stack[-1].kwargs["label"] == "two"


@pytest.mark.parametrize("operation", ["insert_before", "insert_after", "swap"])
def test_relative_operations_reject_missing_targets(
    config, endpoint, events, operation
):
    getattr(config, operation)(Third, Second, events)
    with pytest.raises(ValueError, match="No such middleware"):
        config.build(endpoint)
    assert events == []


@pytest.mark.parametrize("operation", ["move_before", "move_after"])
@pytest.mark.parametrize("target, source", [(First, Third), (Third, First)])
def test_moves_reject_missing_targets_and_sources(
    config, endpoint, events, operation, target, source
):
    config.use(First, events)
    getattr(config, operation)(target, source)
    with pytest.raises(ValueError, match="No such middleware"):
        config.build(endpoint)
    assert events == []


@pytest.mark.parametrize(
    "operation, args",
    [
        ("use", (First,)),
        ("unshift", (First,)),
        ("insert_before", (First, Second)),
        ("insert_after", (First, Second)),
        ("swap", (First, Second)),
        ("delete", (First,)),
        ("move_before", (First, Second)),
        ("move_after", (First, Second)),
        ("build", (None,)),
    ],
)
def test_built_configuration_rejects_changes(config, endpoint, operation, args):
    config.build(endpoint)
    with pytest.raises(RuntimeError, match="frozen"):
        getattr(config, operation)(*args)


def test_stack_exposes_read_only_entries(config, endpoint, events):
    config.use(First, events, label="custom")
    stack = config.build(endpoint)
    assert len(stack) == 1
    assert stack[0].name == "tests.middleware.support.First"
    assert stack[0].args == (events,)
    assert stack[:] == tuple(stack)
    with pytest.raises(TypeError):
        stack[0].kwargs["label"] = "changed"
    with pytest.raises(FrozenInstanceError):
        stack[0].klass = Second
    with pytest.raises(TypeError):
        stack[0] = Middleware(Second)


def test_middleware_can_return_an_early_response(config, endpoint, events):
    config.use(EarlyResponse, message="temporarily unavailable")
    stack = config.build(endpoint)
    with closing(EnvironBuilder()) as builder:
        statuses = []
        response = stack(
            builder.get_environ(), lambda status, headers: statuses.append(status)
        )
        assert list(response) == [b"temporarily unavailable"]
        assert statuses == ["503 SERVICE UNAVAILABLE"]
    assert events == []


def test_stack_preserves_lazy_iteration_and_close(config, events):
    class Body:
        def __iter__(self):
            events.append("iterate")
            yield b"first"
            events.append("resume")
            yield b"second"

        def close(self):
            events.append("close")

    body = Body()
    config.use(First, events)
    stack = config.build(lambda environ, start_response: body)
    events.clear()
    response = stack({}, lambda *args: None)
    assert response is body
    assert events == [("before", "First"), ("after", "First")]
    iterator = iter(response)
    assert next(iterator) == b"first"
    assert "resume" not in events
    response.close()
    assert events[-1] == "close"


def test_middleware_exceptions_propagate_and_unwind(config, events):
    def dispatch(environ, start_response):
        raise RuntimeError("dispatch failed")

    config.use(First, events)
    stack = config.build(dispatch)
    events.clear()
    with pytest.raises(RuntimeError, match="dispatch failed"):
        stack({}, lambda *args: None)
    assert events == [("before", "First"), ("after", "First")]


def test_configuration_rejects_non_callable_factories(config):
    with pytest.raises(TypeError, match="callable"):
        config.use(object())


def test_build_rejects_factories_returning_non_callable_values(config, endpoint):
    config.use(lambda app: None)
    with pytest.raises(TypeError, match="did not return a callable"):
        config.build(endpoint)
