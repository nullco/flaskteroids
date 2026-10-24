import shutil
from pathlib import Path

import pytest

from flaskteroids.application import Application
from flaskteroids.testing import TestDeliveryMethod, TestQueueAdapter

FIXTURES = Path(__file__).parent / "fixtures"


def russian_plural(count):
    if count % 10 == 1 and count % 100 != 11:
        return "one"
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return "few"
    return "many"


@pytest.fixture
def i18n_app_factory(tmp_path):
    applications = []

    def create(name="application", **settings):
        root = tmp_path / name
        shutil.copytree(FIXTURES / "locales", root / "config/locales")

        class LocalizedApplication(Application):
            def configure(self, config):
                config.paths.models = "missing_i18n.models"
                config.paths.helpers = "missing_i18n.helpers"
                config.paths.controllers = "tests.i18n.fixtures.controllers"
                config.paths.jobs = "missing_i18n.jobs"
                config.paths.mailers = "tests.i18n.fixtures.mailers"
                config.paths.routes = "tests.i18n.fixtures.routes"
                config.paths.views = str(FIXTURES / "views")
                config.i18n.available_locales = ["en", "es", "ru"]
                config.i18n.pluralization_rules = {"ru": russian_plural}
                for key, value in settings.items():
                    setattr(config.i18n, key, value)
                config.jobs.queue_adapter = TestQueueAdapter
                config.action_mailer.delivery_method = TestDeliveryMethod
                config.action_mailer.perform_deliveries = True
                config.consider_all_requests_local = True

            def _configure_database(self):
                self.database_url = "sqlite:///:memory:"

        app = LocalizedApplication.initialize(environment="test", root_path=root)
        applications.append(app)
        return app

    yield create
    for app in applications:
        app.extensions["flaskteroids.db"].engine.dispose()


@pytest.fixture
def localized_app(i18n_app_factory):
    return i18n_app_factory()
