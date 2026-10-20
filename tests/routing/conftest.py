from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import request

from flaskteroids.application import Application
from flaskteroids.testing import TestDeliveryMethod, TestQueueAdapter
from tests.routing.app import routes


@pytest.fixture
def make_routing_app(tmp_path, monkeypatch):
    applications = []

    def create(register=None):
        if register is not None:
            monkeypatch.setattr(routes, "register", register)

        class RoutingApplication(Application):
            def configure(self, config):
                config.load_defaults("0.1")
                config.paths.models = "tests.routing.app.models"
                config.paths.controllers = "tests.routing.app.controllers"
                config.paths.routes = "tests.routing.app.routes"
                config.action_controller.allow_forgery_protection = False
                config.active_job.broker_url = "sqla+sqlite:///:memory:"
                config.active_job.queue_adapter = TestQueueAdapter
                config.action_mailer.delivery_method = TestDeliveryMethod

            def _configure_database(self):
                self.database_url = (
                    f"sqlite:///{tmp_path / f'routing-{len(applications)}.sqlite'}"
                )

        app = RoutingApplication.initialize(
            environment="test", root_path=Path(__file__).parent / "app"
        )
        database = app.extensions["flaskteroids.db"]
        database.metadata.create_all(database.engine)
        app.config["TESTING"] = True
        app.config["METHODS"] = []

        @app.after_request
        def observe_method(response):
            app.config["METHODS"].append(request.method)
            return response

        applications.append(app)
        return app

    yield create
    for app in applications:
        app.extensions["flaskteroids.db"].engine.dispose()


@pytest.fixture
def routing_app(make_routing_app):
    return make_routing_app()


@pytest.fixture
def records(routing_app):
    from tests.routing.app.models.records import Category, Product, Subscriber

    with routing_app.test_request_context():
        product = Product.create(name="Product")
        subscriber = Subscriber.create(
            product_id=product.id, email="entered@example.com"
        )
        yield SimpleNamespace(
            product=product,
            subscriber=subscriber,
            new_product=Product.new(name="Entered"),
            new_subscriber=Subscriber.new(
                product_id=product.id, email="entered@example.com"
            ),
            category=Category.create(slug="some-slug"),
        )
