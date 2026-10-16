from __future__ import annotations

from flask import g
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from flaskteroids._models.mapping import discover_models, schema_metadata
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.model import Model, init


def _enable_sqlite_foreign_keys(connection, connection_record):
    autocommit = connection.autocommit
    connection.autocommit = True
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()
    finally:
        connection.autocommit = autocommit


class SQLAlchemyExtension:
    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        if vars(self).get("_app", app) is not app:
            raise ProgrammerError(
                "A database extension cannot be shared between applications."
            )
        if "flaskteroids.db" in app.extensions:
            return
        options = {}
        if make_url(app.database_url).get_backend_name() == "sqlite":
            options["connect_args"] = {"autocommit": False}
        self._engine = create_engine(app.database_url, **options)
        if options:
            event.listen(self._engine, "connect", _enable_sqlite_foreign_keys)
        self._models_module = app.config.paths.models
        try:
            self.init_models()
        except Exception:
            self._engine.dispose()
            raise
        self._session_factory = sessionmaker(
            bind=self._engine, autoflush=False, expire_on_commit=False
        )

        @app.teardown_appcontext
        def teardown(exception=None):
            db_session = g.get("db_session")
            if db_session is None:
                return
            try:
                if db_session.is_active:
                    db_session.rollback()
            finally:
                try:
                    db_session.close()
                finally:
                    g.pop("db_session", None)

        self._app = app
        app.extensions["flaskteroids.db"] = self

    @property
    def engine(self):
        return self._engine

    @property
    def metadata(self):
        return (
            schema_metadata(next(iter(self._models.values())))
            if self._models
            else self._metadata
        )

    @property
    def models(self) -> dict[str, type[Model]]:
        return self._models

    def create_session(self) -> Session:
        return self._session_factory()

    def new_session(self) -> Session:
        return self.create_session()

    def init_models(self):
        if "_models" in vars(self):
            return
        try:
            models = discover_models(self._models_module)
        except ModuleNotFoundError as error:
            if not isinstance(error.name, str) or not (
                error.name == self._models_module
                or self._models_module.startswith(f"{error.name}.")
            ):
                raise
            models = {}
        for model in models.values():
            init(model)
        self._models = models
        self._metadata = next(iter(models.values())).metadata if models else MetaData()

    def require_model(self, model_cls):
        if self._models.get(model_cls.__name__) is not model_cls:
            raise ProgrammerError(
                f"Model {model_cls.__name__} is not registered in this application."
            )
