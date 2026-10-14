from pathlib import Path

import click
from alembic import command
from alembic.util import CommandError
from flask.cli import with_appcontext

from flaskteroids.cli.db.config import get_config


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


@click.command("db:prepare")
@with_appcontext
def prepare():
    """Prepare the selected database with migrations.

    Requires an existing valid db/migrate tree; does not repair migration files,
    reset data, create external databases, or seed records. Uses the current
    environment and honors DATABASE_URL. Start servers in a fresh process.

    \b
    Examples:
      bin/flask db:prepare
      FLASK_ENV=test bin/flask db:prepare
    """
    config = get_config()
    directory = Path(config.get_main_option("script_location"))
    for name in ("alembic.ini", "env.py", "script.py.mako"):
        if not (directory / name).is_file():
            raise CommandError(f"Missing migration resource: {directory / name}")
    if not (directory / "versions").is_dir():
        raise CommandError(f"Missing migration versions directory: {directory}")
    upgrade_database(config)


def upgrade_database(config):
    """Apply migrations using the application's existing Alembic configuration."""
    command.upgrade(config, revision="head")


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
    command.downgrade(config, revision=revision)
