import pytest
from flaskteroids import params
from flaskteroids.actions import after_action, around_action, before_action
from flaskteroids.controller import ActionController, init
from flaskteroids.rules import rules


@pytest.fixture()
def my_controller():

    @rules(
        before_action('_before_first'),
        before_action('_before_second'),
        around_action('_around_first'),
        around_action('_around_second'),
        after_action('_after_first'),
        after_action('_after_second')
    )
    class TestController(ActionController):

        def _before_first(self):
            self.calls = ['before_first']

        def _before_second(self):
            self.calls.append('before_second')

        def _around_first(self):
            self.calls.append('around_first:before')
            yield
            self.calls.append('around_first:after')

        def _around_second(self):
            self.calls.append('around_second:before')
            yield
            self.calls.append('around_second:after')

        def action(self):
            self.calls.append('action')

        def _after_first(self):
            self.calls.append('after_first')

        def _after_second(self):
            self.calls.append('after_second')

    return init(TestController)


def test_controller_flow(my_controller, render_template):
    my_controller().action()
    calls = [
        'before_first',
        'before_second',
        'around_first:before',
        'around_second:before',
        'action',
        'around_second:after',
        'around_first:after',
        'after_first',
        'after_second'
    ]
    render_template.assert_called_with('test/action.html', calls=calls, params=params)
