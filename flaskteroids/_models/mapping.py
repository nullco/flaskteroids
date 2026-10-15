"""Lazy, snapshot-backed mapping of the actual application classes.

Importing a model only registers its declaration. No schema import, mapper or
connection is required until construction, a framework query or a mapped
attribute is requested. A registry belongs to one application model base, not to an engine.
"""

from __future__ import annotations

import pkgutil
from importlib import import_module
from threading import RLock, get_ident

from sqlalchemy import MetaData
from sqlalchemy.orm import MappedColumn, RelationshipProperty, registry

from flaskteroids.declarations import model_for
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.inflector import inflector
from flaskteroids.rules import bind_rules


def _models_module(module):
    parts = module.split(".")
    return ".".join(parts[: parts.index("models") + 1]) if "models" in parts else None


def _root(cls):
    return type.__getattribute__(cls, "_flaskteroids_model_root")


def _load_schema(root):
    if root._flaskteroids_schema_loaded:
        return
    name = root.__schema_module__
    try:
        schema = import_module(name)
    except ModuleNotFoundError as error:
        if error.name == name or name.startswith(f"{error.name}."):
            raise ProgrammerError(
                f"Schema snapshot {name!r} is missing. Run database migrations "
                "or db:schema:dump, then start a fresh process."
            ) from error
        raise
    metadata = vars(schema).get("metadata")
    if not isinstance(metadata, MetaData):
        raise ProgrammerError(
            f"{name} must be a generated schema snapshot with metadata."
        )
    for table in metadata.tables.values():
        copied = table.to_metadata(root.metadata)
        for column in copied.columns:
            if not column.primary_key:
                column.type = column.type.evaluates_none()
    root._flaskteroids_schema_loaded = True


def table_name(cls):
    """Resolve the table convention without requiring a snapshot or mapper."""
    return vars(cls).get("__table_name__", inflector.tableize(cls.__name__))


def _table(cls):
    root = _root(cls)
    name = table_name(cls)
    table = root.metadata.tables.get(name)
    if table is None:
        raise ProgrammerError(
            f"Model {cls.__name__} needs table {name!r} in {root.__schema_module__}. "
            "Run database migrations or db:schema:dump, then start a fresh process."
        )
    if not table.primary_key:
        raise ProgrammerError(
            f"Model {cls.__name__} table {name!r} has no primary key."
        )
    return table


def _native_relationships(cls):
    return {
        name: value
        for base in reversed(cls.__mro__)
        for name, value in vars(base).items()
        if isinstance(value, RelationshipProperty)
    }


def ensure_mapped(cls):
    """Map the requested relationship graph once, using only the snapshot."""
    root = _root(cls)
    if root is None or vars(cls).get("__abstract__", False):
        raise ProgrammerError(f"Abstract model {cls.__name__} cannot be mapped.")
    with root._flaskteroids_mapping_lock:
        if "__mapper__" in vars(cls):
            return cls
        if root._flaskteroids_mapping:
            raise ProgrammerError(
                "Model mapping cannot recursively execute model operations."
            )
        root._flaskteroids_mapping = get_ident()
        try:
            if root.__models_module__:
                discover_models(root.__models_module__)
            _load_schema(root)
            catalog = root._flaskteroids_model_catalog
            graph, tables, properties = [], {}, {}

            def visit(model):
                if model in tables or "__mapper__" in vars(model):
                    return
                bind_rules(model)
                table = _table(model)
                tables[model] = table
                graph.append(model)
                properties[model] = _native_relationships(model)
                for name in table.columns.keys():
                    if any(name in vars(base) for base in model.__mro__):
                        raise ProgrammerError(
                            f"Snapshot field {model.__name__}.{name} conflicts with model API."
                        )
                for name in model_for(model).attachments:
                    if name in table.columns:
                        raise ProgrammerError(
                            f"Attachment {name} conflicts with a model column on {model.__name__}"
                        )
                targets = [
                    association.target
                    for association in model_for(model).associations.values()
                ]
                for relationship in properties[model].values():
                    target = relationship.argument
                    if callable(target) and not isinstance(target, type):
                        target = target()
                    targets.append(target)
                for target in targets:
                    related = catalog.get(target) if isinstance(target, str) else target
                    if related not in catalog.values():
                        raise ProgrammerError(
                            f"Unknown association target {target!r} on {model.__name__}."
                        )
                    visit(related)

            visit(cls)
            # Check the entire graph before publishing a mapper. Missing tables
            # must not poison an otherwise reusable registry during app boot.
            from flaskteroids._models.associations import relationship_properties

            for model in graph:
                properties[model].update(
                    relationship_properties(model, catalog, _table)
                )
            for model in graph:
                root.registry.map_imperatively(
                    model, tables[model], properties=properties[model]
                )
            root.registry.configure()
            return cls
        finally:
            root._flaskteroids_mapping = None


def schema_metadata(model):
    """Load snapshot metadata for schema tooling, without mapping application classes."""
    root = _root(model)
    with root._flaskteroids_mapping_lock:
        _load_schema(root)
        return root.metadata


class SchemaMeta(type):
    def __new__(metaclass, name, bases, namespace, **kwargs):
        namespace = dict(namespace)
        roots = {
            base._flaskteroids_model_root
            for base in bases
            if isinstance(base, SchemaMeta)
            and base._flaskteroids_model_root is not None
        }
        if len(roots) > 1:
            raise ProgrammerError(
                f"{name} inherits multiple application model registries."
            )
        root = next(iter(roots), None)
        for base in bases:
            if isinstance(base, SchemaMeta) and not vars(base).get(
                "__abstract__", False
            ):
                raise ProgrammerError(
                    f"{name} inherits concrete model {base.__name__}; use abstract bases."
                )
        module = namespace.get("__module__", "")
        models_module = _models_module(module)
        schema_module = namespace.get(
            "__schema_module__", root.__schema_module__ if root else None
        )
        abstract = namespace.get("__abstract__", False)
        if root is not None and schema_module != root.__schema_module__:
            raise ProgrammerError(
                "Models cannot change their application's schema module."
            )
        if abstract and root is None:
            if schema_module is None and models_module:
                schema_module = models_module.removesuffix(".models") + ".schema"
            if schema_module:
                owned = registry(metadata=namespace.get("metadata"))
                namespace.update(
                    registry=owned,
                    metadata=owned.metadata,
                    __schema_module__=schema_module,
                )
        if not abstract:
            if root is None:
                raise ProgrammerError(
                    f"{name} needs an abstract application base in <application>.models or with __schema_module__."
                )
            if name in root._flaskteroids_model_catalog:
                raise ProgrammerError(
                    f"Duplicate model name {name!r} in {schema_module!r}."
                )
            if any(
                isinstance(value, MappedColumn) for value in namespace.values()
            ) or any(
                key in namespace
                for key in (
                    "__table__",
                    "__tablename__",
                    "__mapper_args__",
                    "__table_args__",
                    "registry",
                    "metadata",
                )
            ):
                raise ProgrammerError(
                    f"{name} must keep columns/tables in the generated schema snapshot."
                )
        cls = super().__new__(metaclass, name, bases, namespace, **kwargs)
        if abstract and root is None and schema_module:
            cls._flaskteroids_model_root = cls
            cls._flaskteroids_model_catalog = {}
            cls._flaskteroids_mapping_lock = RLock()
            cls._flaskteroids_mapping = None
            cls._flaskteroids_schema_loaded = False
            cls.__models_module__ = namespace.get("__models_module__", models_module)
        elif not abstract:
            root._flaskteroids_model_catalog[name] = cls
        return cls

    def __call__(cls, *args, **kwargs):
        ensure_mapped(cls)
        return super().__call__(*args, **kwargs)

    def __getattr__(cls, name):
        if name.startswith("_") and name not in {
            "__table__",
            "__mapper__",
            "__clause_element__",
        }:
            raise AttributeError(name)
        root = _root(cls)
        if (
            root is None
            or vars(cls).get("__abstract__", False)
            or root._flaskteroids_mapping == get_ident()
        ):
            raise AttributeError(name)
        ensure_mapped(cls)
        if name == "__clause_element__":
            return cls.__mapper__.__clause_element__
        return type.__getattribute__(cls, name)

    def __getattribute__(cls, name):
        value = super().__getattribute__(name)
        if isinstance(value, RelationshipProperty):
            ensure_mapped(cls)
            return type.__getattribute__(cls, name)
        return value


def discover_models(module_name):
    """Discover declarations without importing snapshots or configuring mappers."""
    package = import_module(module_name)
    modules = [package]
    if hasattr(package, "__path__"):
        modules.extend(
            import_module(entry.name)
            for entry in sorted(
                pkgutil.walk_packages(package.__path__, prefix=f"{module_name}."),
                key=lambda entry: entry.name,
            )
        )
    models, roots = {}, set()
    for module in modules:
        for candidate in vars(module).values():
            if (
                isinstance(candidate, SchemaMeta)
                and candidate.__module__ == module.__name__
                and not vars(candidate).get("__abstract__", False)
            ):
                models[candidate.__name__] = candidate
                roots.add(_root(candidate))
    if len(roots) > 1:
        raise ProgrammerError(
            f"{module_name} contains multiple application model registries."
        )
    return dict(sorted(models.items()))


class SchemaModel(metaclass=SchemaMeta):
    __abstract__ = True
    __schema_module__ = None
    _flaskteroids_model_root = None
    registry = None
    metadata = None

    @classmethod
    def prepare(cls):
        """Explicitly prepare mappings for native ORM callers, without database I/O."""
        return ensure_mapped(cls)
