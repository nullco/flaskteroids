from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from flask import g
from sqlalchemy import (
    Column,
    Computed,
    DefaultClause,
    Identity,
    MetaData,
    Table,
    create_engine,
    event,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.orm import Session, registry, sessionmaker

from flaskteroids.declarations import model_for
from flaskteroids.discovery import discover_classes
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.inflector import inflector
from flaskteroids.model import Model, init


@dataclass(frozen=True)
class ResolvedAssociation:
    target: type[Model]
    name: str
    foreign_key: str
    kind: str
    dependent: str | None
    inverse: str | None


@dataclass
class ModelBinding:
    mapped_class: type
    schema: Table
    associations: dict[str, ResolvedAssociation] = field(default_factory=dict)


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


def _row_table(schema):
    """A persistence projection, not a replacement for the reflected schema.

    SQLAlchemy's unit-of-work table sorter resolves even unused foreign keys.
    Associations are application queries, so row mappers need only column/default
    information. Keep the original constraints intact on ModelBinding.schema.
    """
    columns = []
    for column in schema.columns:
        generated = []
        if column.computed is not None:
            generated.append(
                Computed(column.computed.sqltext, persisted=column.computed.persisted)
            )
        if column.identity is not None:
            generated.append(
                Identity(
                    **{
                        name: getattr(column.identity, name)
                        for name in (
                            "always",
                            "on_null",
                            "start",
                            "increment",
                            "minvalue",
                            "maxvalue",
                            "nominvalue",
                            "nomaxvalue",
                            "cycle",
                            "cache",
                            "order",
                        )
                    }
                )
            )
        columns.append(
            Column(
                column.name,
                column.type,
                *generated,
                key=column.key,
                primary_key=column.primary_key,
                nullable=column.nullable,
                autoincrement=column.autoincrement,
                server_default=(
                    DefaultClause(column.server_default.arg)
                    if not generated and column.server_default is not None
                    else None
                ),
                server_onupdate=(
                    DefaultClause(column.server_onupdate.arg, for_update=True)
                    if not generated and column.server_onupdate is not None
                    else None
                ),
            )
        )
    return Table(schema.name, MetaData(), *columns, schema=schema.schema)


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
        self._lock = RLock()
        self._tables = {}
        self._bindings = {}
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False)
        self.init_models()

        @app.teardown_appcontext
        def teardown(exception=None):
            db_session = g.get("db_session")
            if db_session is None:
                return
            try:
                if exception is not None:
                    db_session.rollback()
                else:
                    db_session.commit()
            finally:
                try:
                    db_session.close()
                finally:
                    g.pop("db_session", None)

        self._app = app
        app.extensions["flaskteroids.db"] = self

    def create_session(self) -> Session:
        return self._session_factory()

    def new_session(self) -> Session:
        return self._session_factory()

    @property
    def models(self) -> dict[str, type[Model]]:
        return self._models

    def init_models(self):
        """Register declarations once, without connecting or warming schemas."""
        with self._lock:
            if "_models" in vars(self):
                return
            models = discover_classes(self._models_module, Model, {"ApplicationModel"})
            for model in models.values():
                init(model)
            self._registered = frozenset(models.values())
            self._models = models

    def binding(self, model_cls: type[Model]) -> ModelBinding:
        with self._lock:
            if model_cls not in self._registered:
                raise ProgrammerError(
                    f"Model {model_cls.__name__} is not registered in this application."
                )
            if model_cls in self._bindings:
                return self._bindings[model_cls]
            table_name = inflector.tableize(model_cls.__name__)
            try:
                schema, rows = self._tables.get(table_name, (None, None))
                if schema is None:
                    schema = Table(
                        table_name,
                        MetaData(),
                        autoload_with=self._engine,
                        resolve_fks=False,
                    )
                if not schema.primary_key:
                    raise ProgrammerError(
                        f"Model {model_cls.__name__} table {table_name} is malformed: "
                        "no primary key."
                    )
                for name in model_for(model_cls).attachments:
                    if name in schema.columns:
                        raise ProgrammerError(
                            f"Attachment {name} conflicts with a model column on "
                            f"{model_cls.__name__}"
                        )
                if rows is None:
                    rows = _row_table(schema)
                owned_registry = registry()
                mapped = type(model_cls.__name__, (), {"__table__": rows})
                try:
                    owned_registry.map_imperatively(mapped, rows)
                    owned_registry.configure()
                except Exception:
                    owned_registry.dispose()
                    raise
                binding = ModelBinding(mapped, schema)
            except NoSuchTableError as error:
                raise ProgrammerError(
                    f"No backing table for model {model_cls.__name__} "
                    f"(expected table {table_name}). Did you create/run database migrations? "
                    "Retry after migrating; use a fresh app for already loaded schemas."
                ) from error
            except Exception as error:
                error.add_note(f"While loading {model_cls.__name__} ({table_name})")
                raise
            self._tables[table_name] = schema, rows
            self._bindings[model_cls] = binding
            return binding

    def association(self, model_cls, name):
        """Resolve one declaration; never mutate an already published mapper."""
        with self._lock:
            source = self.binding(model_cls)
            if name in source.associations:
                return source.associations[name]
            try:
                definition = model_for(model_cls).associations[name]
                target_cls = self._models.get(definition.target)
                if target_cls is None:
                    raise ProgrammerError(
                        f"{definition.target} model not found for "
                        f"{model_cls.__name__}.{name}"
                    )
                if name in source.schema.columns:
                    raise ProgrammerError(
                        f"Invalid association {model_cls.__name__}.{name}: "
                        "name conflicts with a model column."
                    )
                target = self.binding(target_cls)
                inverses = [
                    other.name
                    for other in model_for(target_cls).associations.values()
                    if self._models.get(other.target) is model_cls
                    and other.foreign_key == definition.foreign_key
                    and other.kind != definition.kind
                ]
                if len(inverses) > 1:
                    raise ProgrammerError(
                        f"Ambiguous inverse for {model_cls.__name__}.{name}: "
                        f"target {target_cls.__name__}, column {definition.foreign_key}, "
                        f"inverses {', '.join(inverses)}."
                    )
                fk_owner, identity_owner = (
                    (source, target)
                    if definition.kind == "belongs_to"
                    else (target, source)
                )
                if definition.foreign_key not in fk_owner.schema.columns:
                    raise ProgrammerError(
                        f"Invalid association {model_cls.__name__}.{name}: "
                        f"target {target_cls.__name__}, column {definition.foreign_key} "
                        f"does not exist on {fk_owner.schema.name}."
                    )
                if "id" not in identity_owner.schema.columns:
                    raise ProgrammerError(
                        f"Invalid association {model_cls.__name__}.{name}: "
                        f"target {target_cls.__name__}, table {identity_owner.schema.name} "
                        "requires identity column id."
                    )
                for foreign_key in fk_owner.schema.foreign_keys:
                    if foreign_key.parent.name != definition.foreign_key:
                        continue
                    referred_table, _, column_name = (
                        foreign_key.target_fullname.rpartition(".")
                    )
                    if (
                        referred_table == identity_owner.schema.fullname
                        and column_name not in identity_owner.schema.columns
                    ):
                        raise ProgrammerError(
                            f"Invalid association {model_cls.__name__}.{name}: "
                            f"foreign key {foreign_key.target_fullname} references a missing column."
                        )
                association = ResolvedAssociation(
                    target_cls,
                    name,
                    definition.foreign_key,
                    definition.kind,
                    definition.dependent,
                    inverses[0] if inverses else None,
                )
            except Exception as error:
                error.add_note(f"While using {model_cls.__name__}.{name}")
                raise
            source.associations[name] = association
            return association
