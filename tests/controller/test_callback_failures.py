import pytest
from flask import Flask

from flaskteroids.actions import after_action, around_action, before_action
from flaskteroids.controller import Controller, init
from flaskteroids.exceptions import ProgrammerError


@pytest.fixture(scope="module")
def callback_request():
    controllers = []

    def build(
        *,
        before_response=False,
        before_error=None,
        entry_error=None,
        halt=None,
        action_error=None,
        inner_cleanup_error=None,
        outer_cleanup_error=None,
        after_error=None,
    ):
        events = []

        class CallbacksController(Controller):
            before_action("_before")
            around_action("_outer")
            around_action("_inner")
            after_action("_after_first")
            after_action("_after_second")

            def _before(self):
                events.append("before")
                if before_error is not None:
                    raise before_error
                if before_response:
                    return self.head(401)

            def _outer(self):
                events.append("outer:before")
                yield
                events.append("outer:after")
                if outer_cleanup_error is not None:
                    raise outer_cleanup_error

            def _inner(self):
                events.append("inner:before")
                if entry_error is not None:
                    raise entry_error
                if halt is not None:
                    return self.head(403) if halt == "response" else None
                yield
                events.append("inner:after")
                if inner_cleanup_error is not None:
                    raise inner_cleanup_error

            def show(self):
                events.append("action")
                if action_error is not None:
                    raise action_error
                return self.head(202)

            def _after_first(self):
                events.append("after:first")
                if after_error is not None:
                    raise after_error

            def _after_second(self):
                events.append("after:second")

        init(CallbacksController)
        controllers.append(CallbacksController)
        app = Flask(__name__)
        app.testing = True
        app.add_url_rule("/callbacks/", view_func=lambda: CallbacksController().show())
        return app.test_client(), events

    return build


def test_callbacks_wrap_successful_action_in_declared_order(callback_request):
    client, events = callback_request()

    assert client.get("/callbacks/").status_code == 202
    assert events == [
        "before",
        "outer:before",
        "inner:before",
        "action",
        "inner:after",
        "outer:after",
        "after:first",
        "after:second",
    ]


def test_before_response_skips_action_and_other_callbacks(callback_request):
    client, events = callback_request(before_response=True)

    assert client.get("/callbacks/").status_code == 401
    assert events == ["before"]


def test_before_failure_stops_action_and_around_callbacks(callback_request):
    error = ValueError("before failed")
    client, events = callback_request(before_error=error)

    with pytest.raises(ValueError) as raised:
        client.get("/callbacks/")

    assert raised.value is error
    assert events == ["before"]


@pytest.mark.parametrize(
    "error", [ValueError("action failed"), SystemExit("action stopped")]
)
def test_action_failure_resumes_all_around_callbacks(callback_request, error):
    client, events = callback_request(action_error=error)

    with pytest.raises(type(error)) as raised:
        client.get("/callbacks/")

    assert raised.value is error
    assert events == [
        "before",
        "outer:before",
        "inner:before",
        "action",
        "inner:after",
        "outer:after",
    ]


def test_around_setup_failure_unwinds_entered_callbacks(callback_request):
    error = ValueError("setup failed")
    client, events = callback_request(entry_error=error)

    with pytest.raises(ValueError) as raised:
        client.get("/callbacks/")

    assert raised.value is error
    assert events == ["before", "outer:before", "inner:before", "outer:after"]


@pytest.mark.parametrize("halt", ["response", "implicit"])
def test_around_callback_can_halt_before_yield(callback_request, render_template, halt):
    render_template.return_value = "Halted template"
    client, events = callback_request(halt=halt)

    response = client.get("/callbacks/")

    assert response.status_code == (403 if halt == "response" else 200)
    assert events == ["before", "outer:before", "inner:before", "outer:after"]
    if halt == "implicit":
        assert response.text == "Halted template"
    else:
        render_template.assert_not_called()


@pytest.mark.parametrize("failure", ["inner", "outer", "both"])
def test_cleanup_failures_preserve_remaining_cleanup(callback_request, failure):
    inner_error = RuntimeError("inner cleanup failed") if failure != "outer" else None
    outer_error = RuntimeError("outer cleanup failed") if failure != "inner" else None
    client, events = callback_request(
        inner_cleanup_error=inner_error,
        outer_cleanup_error=outer_error,
    )

    with pytest.raises(RuntimeError) as raised:
        client.get("/callbacks/")

    assert raised.value is (inner_error if inner_error is not None else outer_error)
    assert events == [
        "before",
        "outer:before",
        "inner:before",
        "action",
        "inner:after",
        "outer:after",
    ]
    if failure == "both":
        assert any("outer cleanup failed" in note for note in raised.value.__notes__)


@pytest.mark.parametrize("failure", ["setup", "action"])
def test_cleanup_errors_preserve_original_exception(callback_request, caplog, failure):
    error = ValueError(f"{failure} failed")
    client, events = callback_request(
        entry_error=error if failure == "setup" else None,
        action_error=error if failure == "action" else None,
        inner_cleanup_error=RuntimeError("inner cleanup failed"),
        outer_cleanup_error=RuntimeError("outer cleanup failed"),
    )

    with pytest.raises(ValueError) as raised:
        client.get("/callbacks/")

    assert raised.value is error
    assert events[-1] == "outer:after"
    assert "outer cleanup failed" in caplog.text
    assert any("outer cleanup failed" in note for note in error.__notes__)
    if failure == "action":
        assert events[-2] == "inner:after"
        assert "inner cleanup failed" in caplog.text


def test_after_failure_occurs_after_around_cleanup(callback_request):
    error = ValueError("after failed")
    client, events = callback_request(after_error=error)

    with pytest.raises(ValueError) as raised:
        client.get("/callbacks/")

    assert raised.value is error
    assert events[-3:] == ["inner:after", "outer:after", "after:first"]
    assert "after:second" not in events


def test_multiple_around_yields_are_rejected_and_generator_is_closed():
    events = []

    class InvalidController(Controller):
        around_action("_around")

        def _around(self):
            try:
                yield
                yield
            finally:
                events.append("closed")

        def show(self):
            return self.head(200)

    init(InvalidController)
    app = Flask(__name__)
    app.testing = True
    app.add_url_rule("/invalid/", view_func=lambda: InvalidController().show())

    with pytest.raises(ProgrammerError, match="yield exactly once"):
        app.test_client().get("/invalid/")

    assert events == ["closed"]
