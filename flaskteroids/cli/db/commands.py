import click
from flask.cli import with_appcontext
from alembic import command
from flaskteroids.cli.db.config import get_config


@click.command('db:init')
@with_appcontext
def init():
    """Init database migrations"""
    config = get_config()
    directory = config.get_main_option('script_location')
    assert directory
    command.init(config, directory, template='default', package=False)


@click.command('db:migrate')
@with_appcontext
def migrate():
    """Apply database migrations"""
    config = get_config()
    revision = 'head'
    command.upgrade(config, revision=revision)


@click.command('db:rollback')
@with_appcontext
def rollback():
    """Revert database migrations"""
    config = get_config()
    revision = '-1'
    command.downgrade(config, revision=revision)
