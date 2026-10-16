import sqlite3
import traceback

import click
import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from flaskteroids.cli.db.lifecycle import ensure_database


@pytest.mark.parametrize(
    "form", ["relative", "absolute", "uri-relative", "uri-absolute", "uri-escaped"]
)
def test_sqlite_creation_preserves_filename_uri_semantics_and_existing_records(
    tmp_path, monkeypatch, form
):
    monkeypatch.chdir(tmp_path)
    filename = tmp_path / (
        "data name.sqlite" if form == "uri-escaped" else "database.sqlite"
    )
    urls = {
        "relative": "sqlite:///database.sqlite",
        "absolute": f"sqlite+pysqlite:///{filename}",
        "uri-relative": "sqlite:///file:database.sqlite?mode=rwc&cache=shared&uri=true",
        "uri-absolute": f"sqlite:///file:{filename}?mode=rwc&uri=true",
        "uri-escaped": "sqlite:///file:data%20name.sqlite?mode=rwc&uri=true",
    }
    url = urls[form]
    ensure_database(url)
    assert filename.exists()
    with sqlite3.connect(filename) as connection:
        connection.execute("CREATE TABLE records (name TEXT)")
        connection.execute("INSERT INTO records VALUES ('kept')")
    ensure_database(url)
    with sqlite3.connect(filename) as connection:
        assert connection.execute("SELECT name FROM records").fetchall() == [("kept",)]


@pytest.mark.parametrize(
    "url",
    [
        "sqlite://",
        "sqlite:///:memory:",
        "sqlite:///file::memory:?cache=shared&uri=true",
        "sqlite:///file:temporary?mode=memory&uri=true",
        "sqlite:///file:%3Amemory%3A?uri=true",
        "sqlite:///file:?uri=true",
    ],
)
def test_ephemeral_creation_is_rejected_without_connection(url, mocker):
    connect = mocker.patch.object(Engine, "connect")
    with pytest.raises(click.ClickException, match="persistent"):
        ensure_database(url)
    connect.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///file://remote/database?uri=true",
        "sqlite:///database?uri=true",
        "sqlite:///file:database?uri=true&vfs=unknown",
        "sqlite:///file:database?uri=true&mode=invalid",
    ],
)
def test_database_creation_rejects_unsupported_uris_before_connection(url, mocker):
    connect = mocker.patch.object(Engine, "connect")
    with pytest.raises(click.ClickException, match="SQLite"):
        ensure_database(url)
    connect.assert_not_called()


def test_database_creation_reports_missing_parent_with_safe_error(tmp_path):
    parent = tmp_path / "private-password"
    with pytest.raises(click.ClickException) as raised:
        ensure_database(f"sqlite:///{parent / 'database.sqlite'}")
    assert "SQLite" in raised.value.message
    assert "parent directory" in raised.value.message
    assert "private-password" not in raised.value.message
    assert "unable to open database" not in raised.value.message
    assert not parent.exists()
    formatted = "".join(traceback.format_exception(raised.value))
    assert "sqlite3.OperationalError" not in formatted


@pytest.mark.parametrize(
    "url",
    [
        "sqlite+aiosqlite:///database",
        "postgresql+asyncpg://host/database",
        "postgresql+psycopg2://host/database",
        "mysql+mysqldb://host/database",
    ],
)
def test_unsupported_drivers_are_rejected_before_io(url, mocker):
    connect = mocker.patch.object(Engine, "connect")
    with pytest.raises(click.ClickException, match="Unsupported create/prepare driver"):
        ensure_database(url)
    connect.assert_not_called()


@pytest.mark.parametrize("failure", [False, True])
def test_task_connections_and_engines_are_closed_on_every_path(tmp_path, failure):
    connections = []
    disposed = []

    def connected(connection):
        connections.append(connection)

    def execute(connection, cursor, statement, parameters, context, executemany):
        if failure:
            raise OperationalError(
                "do-not-leak", {}, RuntimeError("password-do-not-leak")
            )

    def engine_disposed(engine):
        disposed.append(engine)

    event.listen(Engine, "engine_connect", connected)
    event.listen(Engine, "engine_disposed", engine_disposed)
    event.listen(Engine, "before_cursor_execute", execute)
    try:
        url = f"sqlite:///{tmp_path / 'resources.sqlite'}"
        if failure:
            with pytest.raises(click.ClickException) as raised:
                ensure_database(url)
            assert "do-not-leak" not in raised.value.message
        else:
            ensure_database(url)
    finally:
        event.remove(Engine, "engine_connect", connected)
        event.remove(Engine, "engine_disposed", engine_disposed)
        event.remove(Engine, "before_cursor_execute", execute)
    assert len(disposed) == 1
    assert connections and all(connection.closed for connection in connections)
