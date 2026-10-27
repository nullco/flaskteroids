import io

import pytest
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, create_engine
from werkzeug.datastructures import FileStorage

from flaskteroids.application import Application
from flaskteroids.attachments.schema import metadata as storage_metadata
from flaskteroids.db import session
from flaskteroids.testing import TestDeliveryMethod, TestQueueAdapter


@pytest.fixture
def app(tmp_path):
    url = f"sqlite:///{tmp_path / 'database.sqlite3'}"
    engine = create_engine(url)
    metadata = MetaData()
    Table(
        "documents",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("title", String),
        Column("owner_id", Integer),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
    )
    metadata.create_all(engine)
    storage_metadata.create_all(engine)
    engine.dispose()

    class StorageApplication(Application):
        def configure(self, config):
            config.paths.models = "tests.attachments.app.models"
            config.paths.controllers = "tests.attachments.app.controllers"
            config.paths.routes = "tests.attachments.app.routes"
            config.paths.jobs = "tests.attachments.app.jobs"
            config.paths.mailers = "tests.attachments.app.mailers"
            config.jobs.queue_adapter = TestQueueAdapter
            config.mailer.delivery_method = TestDeliveryMethod
            config.controller.allow_forgery_protection = False
            config.secret_key_base = "storage-test"

        def _configure_database(self):
            self.database_url = url

    return StorageApplication.initialize(environment="test", root_path=tmp_path)


@pytest.fixture
def pending_transaction(app_ctx):
    return session.begin()


@pytest.fixture
def storage(app):
    return app.extensions["flaskteroids.attachments"]


@pytest.fixture
def upload():
    def build(
        data=b"\x89PNG\r\n\x1a\nimage", filename="avatar.png", content_type="image/png"
    ):
        return FileStorage(
            io.BytesIO(data), filename=filename, content_type=content_type
        )

    return build
