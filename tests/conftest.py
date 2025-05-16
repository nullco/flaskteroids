from flaskteroids.app import create_app
import pytest


@pytest.fixture(autouse=True)
def app():
    cfg = {
        'ROUTES_PACKAGE': 'tests.app.config.routes',
        'MODELS_PACKAGE': 'tests.app.models',
        'JOBS_PACKAGE': 'tests.app.jobs',
        'VIEWS_FOLDER': 'tests/app/views/',
        'SQLALCHEMY_URL': 'sqlite:///:memory:',
        'JOBS': {
            'CELERY_BROKER_URL': 'sqla+sqlite:///:memory:'
        },
        'MAIL_ENABLED': False
    }
    app = create_app(__name__, cfg)
    with app.app_context():
        yield
