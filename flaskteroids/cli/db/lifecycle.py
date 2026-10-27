"""Narrow, task-owned database creation. Runtime model use never provisions."""

from contextlib import contextmanager
from urllib.parse import unquote, urlsplit

import click
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.pool import NullPool

_SUPPORTED = {
    "sqlite": "SQLite",
    "sqlite+pysqlite": "SQLite",
    "postgresql+psycopg": "PostgreSQL",
    "mysql+pymysql": "MySQL",
}


def _error_code(error):
    original = error.orig if isinstance(error, DBAPIError) else error
    args = getattr(original, "args", ())
    if args and isinstance(args[0], int):
        return str(args[0])
    code = getattr(original, "sqlstate", None)
    if (
        code is not None
        and len(str(code)) == 5
        and str(code).isascii()
        and str(code).isalnum()
    ):
        return str(code)
    code = getattr(original, "sqlite_errorcode", None)
    if isinstance(code, int):
        return str(code)
    return None


@contextmanager
def _engine(url, **options):
    engine = create_engine(url, poolclass=NullPool, **options)
    try:
        yield engine
    finally:
        engine.dispose()


def _probe(url):
    with _engine(url) as engine, engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def _validate_sqlite(url):
    database = url.database
    if not database or database == ":memory:":
        raise click.ClickException(
            "SQLite create/prepare requires a persistent database; configure a filename. "
            "Use db:migrate for in-memory migration-only workflows."
        )
    uri = str(url.query.get("uri", "false")).lower() in {
        "true",
        "1",
        "yes",
        "on",
        "y",
        "t",
    }
    if not uri:
        return
    parsed = urlsplit(database)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        raise click.ClickException(
            "SQLite create/prepare supports only local persistent file: URIs."
        )
    if (
        not parsed.path
        or unquote(parsed.path) == ":memory:"
        or url.query.get("mode") == "memory"
    ):
        raise click.ClickException(
            "SQLite create/prepare requires a persistent database, not a memory URI."
        )
    supported = {
        "uri",
        "mode",
        "cache",
        "timeout",
        "check_same_thread",
        "detect_types",
        "cached_statements",
    }
    if set(url.query) - supported:
        raise click.ClickException(
            "Unsupported SQLite URI option for create/prepare; use a plain filename or documented URI options."
        )
    if url.query.get("mode", "rwc") not in {"ro", "rw", "rwc"} or url.query.get(
        "cache", "private"
    ) not in {"shared", "private"}:
        raise click.ClickException(
            "Unsupported SQLite URI mode/cache for create/prepare."
        )


def _postgresql(url, maintenance_database):
    if set(url.query) & {"dbname", "database", "service", "options", "replication"}:
        raise click.ClickException(
            "PostgreSQL create/prepare cannot reuse database-specific URL options "
            "(dbname/database/service/options/replication) for maintenance access. "
            "Remove them or provision externally and use db:migrate."
        )
    if (
        not isinstance(maintenance_database, str)
        or not maintenance_database
        or "\0" in maintenance_database
    ):
        raise click.ClickException(
            "Configure database_tasks.maintenance_database as a nonempty database name."
        )
    maintenance = url.set(database=maintenance_database)
    with (
        _engine(maintenance, isolation_level="AUTOCOMMIT") as engine,
        engine.connect() as connection,
    ):
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": url.database},
        ).scalar()
        if not exists:
            identifier = engine.dialect.identifier_preparer.quote_identifier(
                url.database
            )
            try:
                connection.exec_driver_sql(f"CREATE DATABASE {identifier}")
            except DBAPIError as error:
                if _error_code(error) != "42P04":
                    raise
    _probe(url)


def _mysql(url):
    if set(url.query) & {
        "db",
        "database",
        "init_command",
        "read_default_file",
        "read_default_group",
    }:
        raise click.ClickException(
            "MySQL create/prepare cannot reuse database-selecting URL options. "
            "Remove them or provision externally and use db:migrate."
        )
    try:
        _probe(url)
        return
    except DBAPIError as error:
        if _error_code(error) != "1049":
            raise
    with (
        _engine(url.set(database=""), isolation_level="AUTOCOMMIT") as engine,
        engine.connect() as connection,
    ):
        identifier = engine.dialect.identifier_preparer.quote_identifier(url.database)
        try:
            connection.exec_driver_sql(f"CREATE DATABASE {identifier}")
        except DBAPIError as error:
            if _error_code(error) != "1007":
                raise
    _probe(url)


def ensure_database(database_url, *, maintenance_database="postgres"):
    """Ensure one supported persistent target exists and is connectable.

    Every engine/connection belongs to this call. Never mutate the runtime ORM,
    create directories, drop databases, or retry migrations. Error messages must
    not expose URLs, credentials, driver messages, or chained driver tracebacks.
    """
    try:
        url = make_url(database_url)
    except SQLAlchemyError, TypeError, ValueError:
        raise click.ClickException("Invalid database URL for create/prepare.") from None
    backend = _SUPPORTED.get(url.drivername)
    if backend is None:
        raise click.ClickException(
            "Unsupported create/prepare driver. Use sqlite+pysqlite:///, "
            "postgresql+psycopg://, or mysql+pymysql:// with synchronous drivers. "
            "Other runtime drivers may still use db:migrate/db:rollback."
        )
    if backend != "SQLite" and (not url.database or "\0" in url.database):
        raise click.ClickException(
            f"{backend} create/prepare requires an explicit database name."
        )
    try:
        if backend == "SQLite":
            _validate_sqlite(url)
            _probe(url)
        elif backend == "PostgreSQL":
            _postgresql(url, maintenance_database)
        else:
            _mysql(url)
    except (SQLAlchemyError, ImportError, ValueError, TypeError, OSError) as error:
        code = _error_code(error)
        detail = f" (code {code})" if code is not None else ""
        guidance = (
            "Ensure the parent directory exists and SQLite connection options are valid."
            if backend == "SQLite"
            else "Check server access, driver installation, credentials and permissions; "
            "provision the database externally if creation is denied. "
            "PostgreSQL also requires maintenance-database access."
        )
        raise click.ClickException(
            f"{backend} database ensure/connection failed{detail}. {guidance}"
        ) from None
