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
        before_action('_before_greet')
    )
    class GreetController(ActionController):

        def _before_greet(self):
            self.user = 'Bob'

        def greet(self):
            pass

        def _after_greet(self):
            self.shake_hands = True

    register_actions(GreetController, ActionController)
    bind_rules(GreetController)
    return GreetController


def test_controller_generates_template(my_controller, render_template):
    my_controller().greet()
    render_template.assert_called_with('greet/greet.html', user='Bob')


def test_controller_calls_before_actions(my_controller, mocker):
    before_greet = mocker.patch.object(my_controller, '_before_greet', return_value=None)
    my_controller().greet()
    before_greet.assert_called()
