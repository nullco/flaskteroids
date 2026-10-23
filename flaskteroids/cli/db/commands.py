from contextlib import contextmanager
from pathlib import Path

import click
from alembic import command
from alembic.script import ScriptDirectory
from alembic.script.revision import RevisionError
from alembic.util import CommandError
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from flaskteroids.cli.db.config import get_config
from flaskteroids.cli.db.lifecycle import _error_code, ensure_database
from flaskteroids.cli.db.snapshot import dump_schema
from flaskteroids.encryption import generate_encryption_key


@click.command("db:encryption:init")
def encryption_init():
    """Generate dedicated model encryption keys.

    Paste the YAML into flask credentials:edit. Existing credentials are unchanged.
    Do not commit or log the plaintext output. These keys are separate from
    credentials and signing keys.
    """
    click.echo(
        "active_record_encryption:\n"
        f"  primary_key: {generate_encryption_key()}\n"
        f"  deterministic_key: {generate_encryption_key()}"
    )


@click.command("db:init")
@with_appcontext
def init():
    """Set up application database migrations.

    Run from the application root. New applications already do this.
    Requires db/migrate to be absent or empty; does not apply migrations.

    \b
    Example:
      flask db:init
    """
    config = get_config()
    directory = config.get_main_option("script_location")
    assert directory
    command.init(config, directory, template="default", package=False)


@click.command("db:migrate")
@with_appcontext
def migrate():
    """Apply all pending database migrations.

    Run from the application root. Uses the current environment's database.
    Review migrations first; they may change or delete data.

    \b
    Examples:
      flask db:migrate
      FLASK_ENV=test flask db:migrate
    """
    upgrade_database(get_config())


@click.command("db:create")
@with_appcontext
def create():
    """Ensure the selected database exists and is connectable.

    Does not apply migrations, seed records, or start a database server.
    Uses the current environment and DATABASE_URL; no migrations required.

    \b
    Example:
      flask db:create
    """
    ensure_selected_database()
    click.echo("Database is available.")


def ensure_selected_database():
    ensure_database(
        current_app.database_url,
        maintenance_database=current_app.config.database_tasks.maintenance_database,
    )


@click.command("db:prepare")
@with_appcontext
def prepare():
    """Prepare the selected database with migrations.

    Requires an existing valid db/migrate tree; does not repair migration files,
    reset data, or seed records. Ensures the selected supported database exists,
    then applies migrations. Uses the current environment and honors DATABASE_URL.
    Start servers in a fresh process.

    \b
    Examples:
      bin/flask db:prepare
      FLASK_ENV=test bin/flask db:prepare
    """
    config = get_config()
    preflight_migrations(config)
    ensure_selected_database()
    upgrade_database(config)


def preflight_migrations(config):
    directory = Path(config.get_main_option("script_location"))
    for name in ("alembic.ini", "env.py", "script.py.mako"):
        if not (directory / name).is_file():
            raise CommandError(f"Missing migration resource: {directory / name}")
    if not (directory / "versions").is_dir():
        raise CommandError(f"Missing migration versions directory: {directory}")
    try:
        scripts = ScriptDirectory.from_config(config)
        list(scripts.walk_revisions())
        if len(scripts.get_heads()) > 1:
            raise CommandError(
                "Multiple migration heads are unsupported; merge them before preparing."
            )
    except (RevisionError, SyntaxError, ImportError, KeyError) as error:
        raise click.ClickException(
            f"Invalid migration revision graph ({type(error).__name__}); repair migrations before preparing."
        ) from None


def upgrade_database(config):
    """Apply migrations using the application's existing Alembic configuration."""
    with migration_errors("migration"):
        command.upgrade(config, revision="head")
    with migration_errors("schema snapshot (migrations already applied)"):
        dump_schema()


@contextmanager
def migration_errors(operation):
    try:
        yield
    except DBAPIError as error:
        backend = {
            "sqlite": "SQLite",
            "postgresql": "PostgreSQL",
            "mysql": "MySQL",
        }.get(make_url(current_app.database_url).get_backend_name(), "Database")
        code = _error_code(error)
        detail = f" (code {code})" if code is not None else ""
        raise click.ClickException(
            f"{backend} {operation} failed{detail}. Inspect migrations and database access; "
            "the database has been left in place for diagnosis."
        ) from None


@click.command("db:rollback")
@with_appcontext
def rollback():
    """Roll back one database migration.

    Run from the application root. Uses the current environment's database.
    Review rollback code first; generated migrations may need manual reversal
    code, and rollback may delete data.

    \b
    Example:
      flask db:rollback
    """
    config = get_config()
    revision = "-1"
    with migration_errors("rollback"):
        command.downgrade(config, revision=revision)
    with migration_errors("schema snapshot (rollback already applied)"):
        dump_schema()
