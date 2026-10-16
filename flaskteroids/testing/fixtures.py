from pathlib import Path

import yaml
from sqlalchemy import func, inspect, select, text

from flaskteroids._models.attributes import cast_input
from flaskteroids._models.mapping import table_name
from flaskteroids.db import session
from flaskteroids.inflector import inflector


class FixtureSet:
    def __init__(self, records):
        self._records = records

    def __call__(self, label):
        return self._records[label]

    def __getattr__(self, label):
        try:
            return self._records[label]
        except KeyError as error:
            raise AttributeError(label) from error


class FixtureCollection:
    def __init__(self, records=None):
        self._records = records or {}

    def __contains__(self, name):
        return name in self._records

    def __getattr__(self, name):
        try:
            return FixtureSet(self._records[name])
        except KeyError as error:
            raise AttributeError(name) from error


def load_fixtures(application, requested):
    fixture_root = Path(application.project_root, "test", "fixtures")
    if not fixture_root.exists() or not requested:
        return FixtureCollection()

    paths = sorted(fixture_root.glob("*.yml"))
    paths += sorted(fixture_root.glob("*.yaml"))
    if requested != "all":
        names = set(requested)
        paths = [path for path in paths if path.stem in names]

    definitions = {
        path.stem: (yaml.safe_load(path.read_text()) or {}) for path in paths
    }
    models = application.extensions["flaskteroids.db"].models
    fixture_models = {}
    fixture_ids = {}

    for fixture_name, entries in definitions.items():
        model = next(
            (
                candidate
                for candidate in models.values()
                if table_name(candidate) == fixture_name
            ),
            None,
        )
        if model is None:
            raise LookupError(f"No model found for fixture set <{fixture_name}>")
        fixture_models[fixture_name] = model
        fixture_ids[fixture_name] = {
            label: values.get("id", index)
            for index, (label, values) in enumerate(entries.items(), start=1)
        }

    fixture_order = _fixture_order(fixture_models)
    for fixture_name in reversed(fixture_order):
        session.execute(fixture_models[fixture_name].__table__.delete())
    session.flush()

    loaded = {}
    for fixture_name in fixture_order:
        entries = definitions[fixture_name]
        model = fixture_models[fixture_name]
        columns = set(inspect(model).column_attrs.keys())
        loaded[fixture_name] = {}
        for label, original_values in entries.items():
            values = dict(original_values)
            values.setdefault("id", fixture_ids[fixture_name][label])
            for key in list(values):
                foreign_key = f"{key}_id"
                related_set = inflector.pluralize(key)
                related_label = values[key]
                if (
                    key not in columns
                    and foreign_key in columns
                    and related_set in fixture_ids
                    and related_label in fixture_ids[related_set]
                ):
                    values[foreign_key] = fixture_ids[related_set][related_label]
                    values.pop(key)
            converted = {
                key: cast_input(model.__table__.columns[key].type, value)
                for key, value in values.items()
            }
            session.execute(model.__table__.insert().values(**converted))
            loaded[fixture_name][label] = model.find(converted["id"])
        _advance_fixture_sequence(model)

    return FixtureCollection(loaded)


def _advance_fixture_sequence(model):
    """Keep generated IDs above fixtures without rewinding nontransactional sequences."""
    if session.get_bind().dialect.name != "postgresql":
        return
    table = model.__table__
    sequence = session.scalar(
        text(
            "SELECT pg_get_serial_sequence("
            "format('%I.%I', COALESCE(CAST(:schema AS text), current_schema()), "
            "CAST(:table AS text)), 'id')"
        ),
        {"schema": table.schema, "table": table.name},
    )
    maximum = session.scalar(select(func.max(table.c.id)))
    if sequence is not None and maximum is not None:
        session.execute(
            text(
                "SELECT setval(CAST(:sequence AS regclass), "
                "GREATEST(:maximum, nextval(CAST(:sequence AS regclass))), true)"
            ),
            {"sequence": sequence, "maximum": maximum},
        )


def _fixture_order(fixture_models):
    dependencies = {}
    for name, model in fixture_models.items():
        dependencies[name] = {
            foreign_key.target_fullname.rsplit(".", 1)[0]
            for foreign_key in model.__table__.foreign_keys
            if foreign_key.target_fullname.rsplit(".", 1)[0] in fixture_models
        }

    ordered = []
    visited = set()
    visiting = set()

    def visit(name):
        if name in visited:
            return
        if name in visiting:
            return
        visiting.add(name)
        for dependency in dependencies[name]:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)
        ordered.append(name)

    for name in fixture_models:
        visit(name)
    return ordered
