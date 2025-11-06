import pytest
from flaskteroids.helpers import link_to, button_to, form_with, render, csrf_token


@pytest.fixture
def url_for(mocker):
    return mocker.patch('flaskteroids.helpers.url_for')


@pytest.fixture
def model_instance(mocker):
    model_instance = mocker.Mock()
    model_instance.__class__.__name__ = 'TestModel'
    model_instance.id = 1
    model_instance.__json__ = mocker.Mock(return_value={'name': 'test'})
    return model_instance


@pytest.fixture
def render_template(mocker):
    render_template = mocker.patch('flaskteroids.helpers.render_template')
    render_template.return_value = '<div>test</div>'
    return render_template


@pytest.mark.usefixtures('app_ctx')
class TestHelpers:

    def test_link_to_generates_anchor_tag(self):
        result = link_to('Click me', '/test', class_='btn', id='link')
        assert '<a href="/test" class_="btn" id="link">Click me</a>' in str(result)

    def test_button_to_generates_delete_form(self, model_instance, url_for):
        url_for.return_value = '/delete/1'
        result = button_to('Delete', model_instance, 'delete')
        assert 'method="DELETE"' in str(result)
        assert 'action="/delete/1"' in str(result)
        assert '<button type="submit">Delete</button>' in str(result)

    def test_form_with_for_new_model(self, model_instance, url_for):
        url_for.return_value = '/create'
        result = form_with(model=model_instance, caller=lambda _: '<input>')
        assert 'action="/create"' in str(result)
        assert 'method="POST"' in str(result)
        assert '_method' in str(result)

    def test_form_with_for_existing_model(self, model_instance, url_for):
        url_for.return_value = '/update/1'
        result = form_with(model=model_instance)
        assert 'action="/update/1"' in str(result)
        assert 'method="POST"' in str(result)
        assert 'value="PUT"' in str(result)

    def test_render_calls_render_template(self, render_template):
        result = render('test.html', name='value')
        render_template.assert_called_once_with('test.html', name='value')
        assert '<div>test</div>' in str(result)

    def test_csrf_token_generates_token(self):
        result = csrf_token()
        assert result
