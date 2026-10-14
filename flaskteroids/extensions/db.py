import logging
from dataclasses import dataclass, field

from flask import g
from sqlalchemy import MetaData, Table, create_engine, event, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import NoReferencedTableError
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import relationship, sessionmaker

from flaskteroids.declarations import model_for
from flaskteroids.discovery import discover_classes
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.inflector import inflector
from flaskteroids.model import Model, init

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedAssociation:
    target: type
    name: str
    foreign_key: str


@dataclass
class ModelBinding:
    mapped_class: type | None
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
        self._metadata = MetaData()
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

    def create_session(self):
        return self._session_factory()

    def new_session(self):
        return self._session_factory()

    @property
    def models(self):
        return self._models

    def binding(self, model_cls):
        if model_cls not in self._bindings:
            raise ProgrammerError(
                f"Model {model_cls.__name__} is not registered in this application."
            )
        binding = self._bindings[model_cls]
        if binding.mapped_class is None:
            raise ProgrammerError(
                f"No backing table for model {model_cls.__name__}. "
                "Did you create/run database migrations? Construct a fresh application after migrating."
            )
        return binding

    def init_models(self):
        if "_bindings" in vars(self):
            return
        self._models = discover_classes(
            self._models_module, Model, {"ApplicationModel"}
        )
        for model in self._models.values():
            init(model)
        self._reflect_tables()
        base = automap_base(metadata=self._metadata)
        base.prepare(generate_relationship=self._skip_relationships)
        bindings = {
            model: ModelBinding(getattr(base.classes, self._get_table_name(name), None))
            for name, model in self._models.items()
        }
        for model, binding in bindings.items():
            for definition in model_for(model).associations.values():
                target = self._models.get(definition.target)
                if target is None:
                    raise ProgrammerError(
                        f"{definition.target} model not found for {model.__name__}.{definition.name}"
                    )
                binding.associations[definition.name] = ResolvedAssociation(
                    target, definition.name, definition.foreign_key
                )
        for model, binding in bindings.items():
            mapped = binding.mapped_class
            if mapped is None:
                continue
            for definition in model_for(model).associations.values():
                association = binding.associations[definition.name]
                target = bindings[association.target].mapped_class
                if target is None:
                    continue
                inverse = [
                    other.name
                    for other in model_for(association.target).associations.values()
                    if bindings[association.target].associations[other.name].target
                    is model
                    and other.foreign_key == definition.foreign_key
                    and other.kind != definition.kind
                ]
                if len(inverse) > 1:
                    raise ProgrammerError(
                        f"Ambiguous inverse for {model.__name__}.{definition.name}"
                    )
                fk_owner = mapped if definition.kind == "belongs_to" else target
                if definition.foreign_key not in fk_owner.__table__.columns:
                    raise ProgrammerError(
                        f"Invalid association {model.__name__}.{definition.name}: "
                        f"column {definition.foreign_key} does not exist on {fk_owner.__table__.name}."
                    )
                if definition.kind == "belongs_to":
                    fk = getattr(mapped, definition.foreign_key)
                    join = target.id == fk
                    cascade = "save-update, merge"
                else:
                    fk = getattr(target, definition.foreign_key)
                    join = mapped.id == fk
                    cascade = (
                        "all, delete-orphan"
                        if definition.dependent == "destroy"
                        else "save-update, merge"
                    )
                setattr(
                    mapped,
                    definition.name,
                    relationship(
                        target,
                        primaryjoin=join,
                        foreign_keys=[fk],
                        cascade=cascade,
                        back_populates=inverse[0] if inverse else None,
                    ),
                )
            for name in model_for(model).attachments:
                if name in mapped.__table__.columns:
                    raise ProgrammerError(
                        f"Attachment {name} conflicts with a model column on {model.__name__}"
                    )
        base.registry.configure()
        self._bindings = bindings

    def _reflect_tables(self):
        inspector = inspect(self._engine)
        available = set(inspector.get_table_names())
        expected = {self._get_table_name(name) for name in self._models}
        self._metadata.reflect(
            self._engine, only=sorted(expected & available), resolve_fks=False
        )
        tables = list(self._metadata.tables.values())
        for table in tables:
            for constraint in list(table.foreign_key_constraints):
                for foreign_key in constraint.elements:
                    try:
                        _ = foreign_key.column
                    except NoReferencedTableError as error:
                        schema, _, name = error.table_name.rpartition(".")
                        if inspector.has_table(name, schema=schema or None):
                            tables.append(
                                Table(
                                    name,
                                    self._metadata,
                                    schema=schema or None,
                                    autoload_with=self._engine,
                                    resolve_fks=False,
                                )
                            )
                        else:
                            # Automap inspects foreign keys even with automatic relationships disabled.
                            table.constraints.remove(constraint)
                            for element in constraint.elements:
                                table.foreign_keys.discard(element)
                                element.parent.foreign_keys.discard(element)
                            break

    def _get_table_name(self, model_name):
        return inflector.tableize(model_name)

    @staticmethod
    def _skip_relationships(*args, **kwargs):
        pass
