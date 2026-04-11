import pytest


@pytest.fixture(autouse=True)
def render_template(mocker):
    return mocker.patch('flaskteroids.controller.render_template')
