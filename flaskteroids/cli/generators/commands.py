import click
from flask.cli import with_appcontext
import flaskteroids.cli.generators.migrations.generator as migrations
import flaskteroids.cli.generators.model.generator as model


@click.group('generate')
@with_appcontext
def generate():
    pass


@generate.command('migration')
@click.argument('args', nargs=-1)
def generate_migration(args):
    cmd, *cmd_args = args
    migrations.generate(cmd, cmd_args)


@generate.command('model')
@click.argument('args', nargs=-1)
def generate_model(args):
    model_name, *cmd_args = args
    model.generate(model_name, cmd_args)
