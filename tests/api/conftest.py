import pytest

from flaskteroids.application import Application
from flaskteroids.testing import TestDeliveryMethod, TestQueueAdapter


@pytest.fixture
def api_application_factory(tmp_path):
    applications = []

    def create(*, api_only=True):
        class ExampleApplication(Application):
            def configure(self, config):
                config.api_only = api_only
                config.paths.controllers = "tests.api.application.controllers"
                config.paths.models = "missing.models"
                config.paths.routes = "tests.api.application.routes"
                config.paths.mailers = "missing.mailers"
                config.paths.jobs = "missing.jobs"
                config.paths.helpers = "missing.helpers"
                config.jobs.queue_adapter = TestQueueAdapter
                config.action_mailer.delivery_method = TestDeliveryMethod
                config.secret_key_base = "test-signing-key"

            def _configure_database(self):
                self.database_url = "sqlite:///:memory:"

        app = ExampleApplication.initialize(environment="test", root_path=tmp_path)
        applications.append(app)
        return app

    yield create

    for app in applications:
        app.extensions["flaskteroids.db"].engine.dispose()


@pytest.fixture
def api_app(api_application_factory):
    return api_application_factory()


@pytest.fixture
def api_client(api_app):
    return api_app.test_client()
