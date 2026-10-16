import importlib
from datetime import datetime
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from flask import Flask

from flaskteroids.cli.db.snapshot import dump, dump_schema
from flaskteroids.extensions.db import SQLAlchemyExtension


@pytest.fixture
def snapshot_app(discovery_package, tmp_path):
    package = discovery_package(
        {
            "__init__.py": "",
            "app/models/__init__.py": "",
            "app/models/application_model.py": (
                "from flaskteroids.model import Model\n"
                "class ApplicationModel(Model):\n    __abstract__ = True\n"
            ),
            "app/models/entry.py": (
                "from .application_model import ApplicationModel\n"
                "class Entry(ApplicationModel): pass\n"
            ),
        }
    )
    app = Flask(__name__)
    app.project_root = tmp_path / package
    app.database_url = f"sqlite:///{tmp_path / 'snapshot.sqlite'}"
    app.config.paths = SimpleNamespace(models=f"{package}.app.models")
    db = SQLAlchemyExtension(app)
    metadata = sa.MetaData()
    sa.Table("categories", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    entries = sa.Table(
        "entries",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), server_default=sa.text("'O''Reilly'")),
        sa.Column("quantity", sa.Integer(), server_default=sa.text("7")),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("settings", sa.JSON(), server_default=sa.text("'{}'")),
        sa.Column(
            "category_id", sa.ForeignKey("categories.id", name="fk_entries_category")
        ),
        sa.Column(
            "generated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column("doubled", sa.Integer(), sa.Computed("quantity * 2")),
        sa.UniqueConstraint("name", name="unique_entries_name"),
        sa.CheckConstraint("quantity >= 0", name="positive_quantity"),
    )
    sa.Index("index_entries_category", entries.c.category_id)
    sa.Table("alembic_version", metadata, sa.Column("version_num", sa.String(32)))
    metadata.create_all(db.engine)
    yield SimpleNamespace(
        app=app,
        db=db,
        package=package,
        path=tmp_path / package / "db/schema.py",
        Entry=db.models["Entry"],
    )
    db.engine.dispose()


def test_dump_is_database_derived_deterministic_and_importable_without_io(
    snapshot_app, mocker
):
    state = snapshot_app
    assert not state.path.exists()
    assert "__mapper__" not in vars(state.Entry)
    assert dump_schema(state.app) == state.path
    original = state.path.read_bytes()
    assert b"Generated from the database" in original
    assert dump_schema(state.app).read_bytes() == original
    connect = mocker.patch(
        "sqlalchemy.engine.Engine.connect",
        side_effect=AssertionError("unexpected connection"),
    )
    schema = importlib.import_module(f"{state.package}.db.schema")
    assert set(schema.metadata.tables) == {"categories", "entries"}
    assert not hasattr(schema, "Entry")
    table = schema.metadata.tables["entries"]
    assert table.c.name.type.length == 255
    assert table.c.doubled.computed is not None
    assert {fk.target_fullname for fk in table.foreign_keys} == {"categories.id"}
    assert {index.name for index in table.indexes} == {"index_entries_category"}
    assert {constraint.name for constraint in table.constraints} >= {
        "unique_entries_name",
        "positive_quantity",
    }
    assert state.Entry.prepare() is state.Entry
    assert "categories" in state.Entry.metadata.tables
    connect.assert_not_called()


def test_literal_defaults_are_available_on_new_models_but_functions_run_on_server(
    snapshot_app,
):
    state = snapshot_app
    dump_schema(state.app)
    first, second = state.Entry(), state.Entry()
    assert first.name == "O'Reilly"
    assert first.quantity == 7
    assert first.enabled is False
    assert first.settings == second.settings == {}
    assert first.settings is not second.settings
    assert first.generated_at is None
    assert first.doubled is None
    with state.app.app_context():
        assert first.save()
        assert first.doubled == 14
        assert isinstance(first.generated_at, datetime)


def test_explicit_null_overrides_server_default(snapshot_app):
    state = snapshot_app
    dump_schema(state.app)
    with state.app.app_context():
        entry = state.Entry.create(
            name=None, quantity=None, enabled=None, settings=None
        )
        assert entry.reload().name is None
        assert entry.quantity is None
        assert entry.enabled is None
        assert entry.settings is None
        assert entry.doubled is None


def test_failed_publication_preserves_previous_snapshot_and_removes_temporary_file(
    snapshot_app, mocker
):
    state = snapshot_app
    dump_schema(state.app)
    original = state.path.read_bytes()
    before = set(state.path.parent.iterdir())
    mocker.patch(
        "flaskteroids.cli.db.snapshot.os.replace",
        side_effect=PermissionError("read only"),
    )
    with pytest.raises(PermissionError):
        dump_schema(state.app)
    assert state.path.read_bytes() == original
    assert set(state.path.parent.iterdir()) == before


def test_dump_command_refreshes_snapshot_without_loading_model_mappings(snapshot_app):
    state = snapshot_app
    state.app.cli.add_command(dump)
    result = state.app.test_cli_runner().invoke(args=["db:schema:dump"])
    assert result.exit_code == 0, result.output
    assert state.path.exists()
    assert "__mapper__" not in vars(state.Entry)


def test_snapshot_publication_preserves_read_permissions(snapshot_app):
    import stat

    state = snapshot_app
    dump_schema(state.app)
    assert stat.S_IMODE(state.path.stat().st_mode) == 0o644
    state.path.chmod(0o640)
    dump_schema(state.app)
    assert stat.S_IMODE(state.path.stat().st_mode) == 0o640
