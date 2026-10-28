import pytest
from jinja2 import DictLoader
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
)

from flaskteroids.application import Application
from flaskteroids.attachments.schema import metadata as attachment_metadata
from flaskteroids.testing import TestDeliveryMethod, TestQueueAdapter


@pytest.fixture
def make_app(tmp_path):
    applications = []

    def create(
        name,
        tables=("authors", "stories"),
        adapter=TestQueueAdapter,
        application_class=Application,
    ):
        root = tmp_path / name
        root.mkdir(exist_ok=True)
        url = f"sqlite:///{root / 'database.sqlite'}"
        metadata = MetaData()
        Table(
            "authors",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("name", String),
            Column("passcode_digest", String),
            Column("created_at", DateTime),
            Column("updated_at", DateTime),
        )
        Table(
            "stories",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("title", String),
            Column("author_id", ForeignKey("authors.id")),
            Column("editor_id", ForeignKey("authors.id")),
            Column("created_at", DateTime),
            Column("updated_at", DateTime),
        )
        engine = create_engine(url)
        metadata.create_all(engine, tables=[metadata.tables[table] for table in tables])
        attachment_metadata.create_all(engine)
        engine.dispose()

        class IsolatedApplication(application_class):
            def configure(self, config):
                config.paths.models = "tests.isolation.models"
                config.paths.jobs = "tests.isolation.jobs"
                config.paths.mailers = "tests.isolation.mailers"
                config.paths.controllers = "tests.isolation.controllers"
                config.paths.routes = "tests.isolation.routes"
                config.jobs.queue_adapter = adapter
                config.jobs.broker_url = "memory://"
                config.jobs.result_backend = "cache+memory://"
                config.jobs.additional_config.task_always_eager = True
                config.mailer.delivery_method = TestDeliveryMethod
                config.mailer.perform_deliveries = True
                config.mailer.default_options = {"by": f"{name}@example.org"}
                config.controller.allow_forgery_protection = False
                config.secret_key_base = f"{name}-secret"

            def _configure_database(self):
                self.database_url = url

        app = IsolatedApplication.initialize(environment="test", root_path=root)
        applications.append(app)
        app.config["OWNER"] = name
        app.config["EVENTS"] = []
        app.jinja_loader = DictLoader({"notice_mailer/notice.txt": name})
        return app

    yield create
    for app in applications:
        app.extensions["flaskteroids.db"].engine.dispose()
