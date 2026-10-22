import pytest
from jinja2 import DictLoader

from flaskteroids.application import Application
from flaskteroids.testing import TestDeliveryMethod, TestQueueAdapter


@pytest.fixture
def view_app_factory(tmp_path):
    applications = []

    def create(
        *, include_all=True, helpers="tests.views.fixtures.helpers", owners=True
    ):
        class ViewApplication(Application):
            def configure(self, config):
                config.paths.models = "missing.models"
                config.paths.jobs = "missing.jobs"
                config.paths.helpers = helpers
                config.paths.controllers = (
                    "tests.views.fixtures.controllers"
                    if owners
                    else "missing.controllers"
                )
                config.paths.mailers = (
                    "tests.views.fixtures.mailers" if owners else "missing.mailers"
                )
                config.paths.routes = "tests.views.fixtures.routes"
                config.action_controller.include_all_helpers = include_all
                config.active_job.queue_adapter = TestQueueAdapter
                config.action_mailer.delivery_method = TestDeliveryMethod
                config.action_mailer.perform_deliveries = True

            def _configure_database(self):
                self.database_url = "sqlite:///:memory:"

        app = ViewApplication.initialize(environment="test", root_path=tmp_path)
        app.jinja_loader = DictLoader({"probe.html": ""})
        app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=True)
        applications.append(app)
        return app

    yield create
    for app in applications:
        app.extensions["flaskteroids.db"].engine.dispose()
