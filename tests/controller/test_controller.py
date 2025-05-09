import pytest
from flaskteroids.actions import register_actions, before_action
from flaskteroids.controller import ActionController
from flaskteroids.rules import bind_rules, rules


@pytest.fixture(autouse=True)
def render_template(mocker):
    return mocker.patch('flaskteroids.controller.render_template')


@pytest.fixture()
def my_controller():

    @rules(
        before_action('_before')
    )
    class GreetController(ActionController):

        def _before(self):
            pass

        def index(self):
            pass

    register_actions(GreetController, ActionController)
    bind_rules(GreetController)
    return GreetController


def test_controller_generates_template(my_controller, render_template):
    my_controller().index()
    render_template.assert_called_with('greet/index.html')


def test_controller_calls_before_actions(my_controller, mocker):
    before = mocker.patch.object(my_controller, '_before', return_value=None)
    my_controller().index()
    before.assert_called()
