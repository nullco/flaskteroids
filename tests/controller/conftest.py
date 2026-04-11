import pytest


@pytest.fixture(autouse=True)
def render_template(mocker):
    return mocker.patch('cucurbit.controller.render_template')
