import pytest

from flaskteroids.actions import after_action, around_action, before_action
from flaskteroids.controller import ActionController, init


@pytest.fixture()
def my_controller():

    class TestController(ActionController):
        before_action("_before_first")
        before_action("_before_second")
        around_action("_around_first")
        around_action("_around_second")
        after_action("_after_first")
        after_action("_after_second")

        def _before_first(self):
            self.calls = ["before_first"]

        def _before_second(self):
            self.calls.append("before_second")

        def _around_first(self):
            self.calls.append("around_first:before")
            yield
            self.calls.append("around_first:after")

        def _around_second(self):
            self.calls.append("around_second:before")
            yield
            self.calls.append("around_second:after")

        def action(self):
            self.calls.append("action")

        def _after_first(self):
            self.calls.append("after_first")

        def _after_second(self):
            self.calls.append("after_second")

    return init(TestController)


@pytest.mark.usefixtures("app_ctx")
def test_controller_runs_callbacks_in_order_and_renders_action(
    my_controller, render_template
):
    controller = my_controller()
    controller.action()
    calls = [
        "before_first",
        "before_second",
        "around_first:before",
        "around_second:before",
        "action",
        "around_second:after",
        "around_first:after",
        "after_first",
        "after_second",
    ]
    render_template.assert_called_with(
        "test/action.html", calls=calls, params=controller.params
    )
