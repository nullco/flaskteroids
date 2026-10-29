import pytest
from flask.cli import FlaskGroup


@pytest.fixture
def bootless_cli(mocker):
    create_app = mocker.Mock(side_effect=AssertionError("Application loaded too early"))
    yield FlaskGroup(create_app=create_app)
    create_app.assert_not_called()
