from flaskteroids.app import create_app
import pytest


@pytest.fixture
def app():
    app = create_app(__name__)
    with app.app_context():
        yield
