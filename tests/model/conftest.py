from contextlib import ExitStack
from types import SimpleNamespace

import pytest
from flask import Flask, has_app_context
from sqlalchemy import create_engine

from flaskteroids.db import session as db_session
from flaskteroids.extensions.db import SQLAlchemyExtension


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'models.sqlite'}", connect_args={"autocommit": False}
    )
    yield engine
    engine.dispose()


@pytest.fixture
def session():
    return db_session._get_current_object()


@pytest.fixture
def current_app():
    from flask import current_app

    return current_app


@pytest.fixture
def init_models(engine, mocker):
    with ExitStack() as contexts:

        def initialize(base, model_base_tuples):
            if has_app_context():
                db_session.commit()
            base.metadata.create_all(engine)
            app = Flask(__name__)
            app.config["SECRET_KEY"] = "test"
            app.config.paths = SimpleNamespace(models="test_models")
            app.database_url = str(engine.url)
            mocker.patch(
                "flaskteroids.extensions.db.discover_classes",
                return_value={model.__name__: model for _, model in model_base_tuples},
            )
            mocker.patch(
                "flaskteroids.extensions.db.create_engine", return_value=engine
            )
            SQLAlchemyExtension(app)
            contexts.enter_context(app.app_context())

        yield initialize
