import click
from flask.cli import with_appcontext
from alembic import command
from flaskteroids.cli.db.config import get_config


@click.command('db:init')
@with_appcontext
def init():
    config = get_config()
    directory = config.get_main_option('script_location')
    assert directory
    command.init(config, directory, template='default', package=False)


@click.command('db:migrate')
def migrate():
    config = get_config()
    revision = 'head'
    command.upgrade(config, revision=revision)
