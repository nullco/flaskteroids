import pytest
from flaskteroids.actions import after_action, around_action, before_action
from flaskteroids.controller import ActionController, init
from flaskteroids.rules import rules


@pytest.fixture(autouse=True)
def render_template(mocker):
    return mocker.patch('flaskteroids.controller.render_template')


@pytest.fixture()
def my_controller():

    @rules(
        before_action('_before'),
        around_action('_around'),
        after_action('_after')
    )
    class TestController(ActionController):

        def _before(self):
            self.calls = ['before']

        def _around(self):
            self.calls.append('around:before')
            yield
            self.calls.append('around:after')

        def action(self):
            self.calls.append('action')

        def _after(self):
            self.calls.append('after')

    return init(TestController)


def test_controller_flow(my_controller, render_template):
    my_controller().action()
    calls = ['before', 'around:before', 'action', 'around:after', 'after']
    render_template.assert_called_with('test/action.html', calls=calls)
