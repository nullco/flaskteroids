import pytest

from flaskteroids.application import Application
from flaskteroids.testing import TestDeliveryMethod, TestQueueAdapter


@pytest.fixture
def app(tmp_path):
    url = f"sqlite:///{tmp_path / 'rich_text.sqlite3'}"

    class RichTextApplication(Application):
        def configure(self, config):
            config.paths.models = "tests.rich_text.app.models"
            config.paths.controllers = "tests.rich_text.app.controllers"
            config.paths.routes = "tests.rich_text.app.routes"
            config.paths.jobs = "tests.rich_text.app.jobs"
            config.paths.mailers = "tests.rich_text.app.mailers"
            config.active_job.queue_adapter = TestQueueAdapter
            config.action_mailer.delivery_method = TestDeliveryMethod
            config.action_controller.allow_forgery_protection = False

        def _configure_database(self):
            self.database_url = url

    application = RichTextApplication.initialize(environment="test", root_path=tmp_path)
    db = application.extensions["flaskteroids.db"]
    db.metadata.create_all(db.engine)
    try:
        yield application
    finally:
        db.engine.dispose()
