import pytest
from flask import Flask

from flaskteroids.actions import after_action, around_action, before_action
from flaskteroids.controller import ActionController, init
from flaskteroids.exceptions import ProgrammerError


@pytest.fixture
def app_context():
    with Flask(__name__).app_context():
        yield


@pytest.mark.usefixtures("app_context")
@pytest.mark.parametrize("hook", [before_action, around_action, after_action])
@pytest.mark.parametrize("selection", [None, [], (), ["index"]])
def test_hooks_apply_selection_filters_and_preserve_registration_order(hook, selection):
    events = []
    method = "_around" if hook is around_action else "_callback"

    class Example(ActionController):
        hook(method, only=selection)
        hook(method, only=selection)

        def _callback(self):
            events.append("callback")

        def _around(self):
            events.append("enter")
            yield
            events.append("exit")

        def index(self):
            events.append("index")
            return "index response"

        def extra(self):
            events.append("extra")
            return "extra response"

    init(Example)
    init(Example)
    instance = Example()
    instance.index()
    instance.extra()
    if hook is before_action:
        assert events == ["callback", "callback", "index"] + (
            ["extra"] if selection else ["callback", "callback", "extra"]
        )
    elif hook is around_action:
        assert events == ["enter", "enter", "index", "exit", "exit"] + (
            ["extra"] if selection else ["enter", "enter", "extra", "exit", "exit"]
        )
    else:
        assert events == ["index", "callback", "callback"] + (
            ["extra"] if selection else ["extra", "callback", "callback"]
        )


@pytest.mark.parametrize("hook", [before_action, around_action, after_action])
@pytest.mark.parametrize(
    "method,error", [("public", ProgrammerError), ("_missing", AttributeError)]
)
def test_hooks_reject_invalid_names_and_missing_methods(hook, method, error):
    class Example(ActionController):
        hook(method)

        def index(self):
            return "response"

    with pytest.raises(error):
        init(Example)
