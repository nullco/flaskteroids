import importlib
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from flaskteroids.application import Application
from flaskteroids.testing import TestDeliveryMethod, TestQueueAdapter
from tests.generated_application import generated_app_factory as generated_app_factory
from tests.generated_application import generated_scaffolds as generated_scaffolds
from tests.generated_application import generated_store as generated_store


@pytest.fixture
def discovery_package(tmp_path, monkeypatch):
    name = f"discovery_{uuid4().hex}"
    monkeypatch.syspath_prepend(str(tmp_path))

    def create(files):
        for relative, source in files.items():
            path = tmp_path / name / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source)
        importlib.invalidate_caches()
        return name

    yield create
    for module in list(sys.modules):
        if module == name or module.startswith(f"{name}."):
            del sys.modules[module]
    importlib.invalidate_caches()


@pytest.fixture
def app(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'application.sqlite'}"

    class TestApplication(Application):
        def configure(self, config):
            config.load_defaults("0.1")
            config.paths.models = "tests.app.models"
            config.paths.views = "app/views"
            config.paths.controllers = "tests.app.controllers"
            config.paths.routes = "tests.app.config.routes"
            config.paths.jobs = "tests.app.jobs"
            config.paths.mailers = "tests.app.mailers"
            config.active_job.broker_url = "sqla+sqlite:///:memory:"
            config.active_job.queue_adapter = TestQueueAdapter
            config.action_mailer.delivery_method = TestDeliveryMethod
            config.action_mailer.perform_deliveries = True

        def _configure_database(self):
            self.database_url = db_url

    application = TestApplication.initialize(
        environment="test",
        root_path=Path(__file__).parent,
    )
    database = application.extensions["flaskteroids.db"]
    database.metadata.create_all(database.engine)
    try:
        yield application
    finally:
        database.engine.dispose()


@pytest.fixture
def app_ctx(app):
    with app.app_context():
        yield


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def cli_runner(app):
    return app.test_cli_runner()
