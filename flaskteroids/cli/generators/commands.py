import click
from flask.cli import with_appcontext
import flaskteroids.cli.generators.migrations.generator as migrations


@click.group('generate')
@with_appcontext
def generate():
    pass


@generate.command('migration')
@click.argument('args', nargs=-1)
def generate_migration(args):
    cmd, *cmd_args = args
    migrations.migration(cmd, cmd_args)
