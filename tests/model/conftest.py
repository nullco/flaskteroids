from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, has_app_context
from sqlalchemy import create_engine

from flaskteroids.db import session as db_session
from flaskteroids.extensions.db import SQLAlchemyExtension
from tests.model.through_support import network as network


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
                "flaskteroids.extensions.db.discover_models",
                return_value={model.__name__: model for _, model in model_base_tuples},
            )
            mocker.patch(
                "flaskteroids.extensions.db.create_engine", return_value=engine
            )
            SQLAlchemyExtension(app)
            contexts.enter_context(app.app_context())

        yield initialize


@pytest.fixture
def mapped_app(discovery_package, tmp_path):
    source = Path(__file__).parent / "fixtures/mapped_records"
    package = discovery_package(
        {
            "__init__.py": "",
            "app/models/__init__.py": "",
            **{
                str(path.relative_to(source)): path.read_text()
                for path in source.rglob("*.py")
            },
        }
    )
    app = Flask(__name__)
    app.secret_key = "test"
    app.add_url_rule("/authors/", endpoint="create_author", view_func=lambda: "")
    app.add_url_rule(
        "/authors/<int:id>/", endpoint="update_author", view_func=lambda id: ""
    )
    app.database_url = f"sqlite:///{tmp_path / 'mapped.sqlite'}"
    app.config.paths = SimpleNamespace(models=f"{package}.app.models")
    db = SQLAlchemyExtension(app)
    db.metadata.create_all(db.engine)
    yield app
    db.engine.dispose()


@pytest.fixture
def records(mapped_app):
    with mapped_app.app_context():
        db = mapped_app.extensions["flaskteroids.db"]
        yield SimpleNamespace(
            app=mapped_app,
            db=db,
            session=db_session,
            Author=db.models["Author"],
            Post=db.models["Post"],
        )
