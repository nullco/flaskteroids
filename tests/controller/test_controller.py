import pytest
from flaskteroids.actions import after_action, before_action
from flaskteroids.controller import ActionController, init
from flaskteroids.rules import rules


@pytest.fixture(autouse=True)
def render_template(mocker):
    return mocker.patch('flaskteroids.controller.render_template')


@pytest.fixture()
def my_controller():

    @rules(
        before_action('_before_greet'),
        after_action('_after_greet')
    )
    class GreetController(ActionController):

        def _before_greet(self):
            self.user = 'Bob'

        def greet(self):
            pass

        def _after_greet(self):
            self.shake_hands = True

    init(GreetController)
    return GreetController


def test_controller_generates_template(my_controller, render_template):
    my_controller().greet()
    render_template.assert_called_with('greet/greet.html', user='Bob', shake_hands=True)


def test_controller_calls_before_actions(my_controller, mocker):
    before_greet = mocker.patch.object(my_controller, '_before_greet', return_value=None)
    my_controller().greet()
    before_greet.assert_called()


def test_controller_calls_after_actions(my_controller, mocker):
    after_greet = mocker.patch.object(my_controller, '_after_greet', return_value=None)
    my_controller().greet()
    after_greet.assert_called()
