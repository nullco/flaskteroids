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
                f"No backing table for model {model_cls.__name__} "
                f"(expected table {self._get_table_name(model_cls.__name__)}). "
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
        available_tables = self._reflect_tables()
        base = automap_base(metadata=self._metadata)
        base.prepare(generate_relationship=self._skip_relationships)
        bindings = {}
        for name, model in self._models.items():
            table_name = self._get_table_name(name)
            mapped = getattr(base.classes, table_name, None)
            if mapped is None and table_name in available_tables:
                table = self._metadata.tables[table_name]
                reason = (
                    "no primary key" if not table.primary_key else "no usable mapping"
                )
                raise ProgrammerError(
                    f"Model {model.__name__} table {table_name} is malformed: {reason}."
                )
            bindings[model] = ModelBinding(mapped)
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
        configured_associations = []
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
                        f"Ambiguous inverse for {model.__name__}.{definition.name}: "
                        f"target {association.target.__name__}, column {definition.foreign_key}, "
                        f"inverses {', '.join(inverse)}."
                    )
                fk_owner = mapped if definition.kind == "belongs_to" else target
                if definition.foreign_key not in fk_owner.__table__.columns:
                    raise ProgrammerError(
                        f"Invalid association {model.__name__}.{definition.name}: "
                        f"target {association.target.__name__}, column {definition.foreign_key} "
                        f"does not exist on {fk_owner.__table__.name}."
                    )
                identity_owner = target if definition.kind == "belongs_to" else mapped
                if "id" not in identity_owner.__table__.columns:
                    raise ProgrammerError(
                        f"Invalid association {model.__name__}.{definition.name}: "
                        f"target {association.target.__name__}, table {identity_owner.__table__.name} "
                        "requires identity column id."
                    )
                try:
                    fk = getattr(fk_owner, definition.foreign_key)
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
                            primaryjoin=identity_owner.id == fk,
                            foreign_keys=[fk],
                            cascade=cascade,
                            back_populates=inverse[0] if inverse else None,
                        ),
                    )
                except Exception as error:
                    error.add_note(
                        f"While configuring {model.__name__}.{definition.name}: "
                        f"target {association.target.__name__} ({target.__table__.name}), "
                        f"foreign key {fk_owner.__table__.name}.{definition.foreign_key}"
                    )
                    raise
                configured_associations.append(f"{model.__name__}.{definition.name}")
            for name in model_for(model).attachments:
                if name in mapped.__table__.columns:
                    raise ProgrammerError(
                        f"Attachment {name} conflicts with a model column on {model.__name__}"
                    )
        try:
            base.registry.configure()
        except Exception as error:
            # Configuration checks the entire registry, not just the last relationship.
            models = ", ".join(model.__name__ for model in bindings)
            associations = ", ".join(configured_associations)
            error.add_note(
                f"While configuring application mappings for {models}; "
                f"associations: {associations}"
            )
            raise
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
        return available

    def _get_table_name(self, model_name):
        return inflector.tableize(model_name)

    @staticmethod
    def _skip_relationships(*args, **kwargs):
        pass
