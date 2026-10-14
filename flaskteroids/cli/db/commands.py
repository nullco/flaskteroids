import click
from flask.cli import with_appcontext
from alembic import command
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
    config = get_config()
    revision = "head"
    command.upgrade(config, revision=revision)


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
