import click
from flask.cli import with_appcontext
import flaskteroids.cli.generators.migrations.generator as migrations
import flaskteroids.cli.generators.model.generator as model
import flaskteroids.cli.generators.resource.generator as resource
import flaskteroids.cli.generators.scaffold.generator as scaffold
import flaskteroids.cli.generators.controller.generator as controller
import flaskteroids.cli.generators.mailer.generator as mailer
import flaskteroids.cli.generators.authentication.generator as authentication


@click.group()
@with_appcontext
def generate():
    """Generate commands"""
    pass


@generate.command('migration')
@click.argument('args', nargs=-1)
def generate_migration(args):
    """Migration generator"""
    cmd, *cmd_args = args
    migrations.generate(cmd, cmd_args)


@generate.command('model')
@click.argument('args', nargs=-1)
def generate_model(args):
    """Model generator"""
    model_name, *cmd_args = args
    model.generate(model_name, cmd_args)


@generate.command('controller')
@click.argument('name')
@click.argument('actions', nargs=-1)
@click.option('--skip-routes', is_flag=True)
def generate_controller(name, actions, skip_routes):
    """Controller generator"""
    controller.generate(name, actions, skip_routes)


@generate.command('mailer')
@click.argument('name')
@click.argument('actions', nargs=-1)
def generate_mailer(name, actions):
    """Mailer generator"""
    mailer.generate(name, actions)


@generate.command('scaffold')
@click.argument('args', nargs=-1)
def generate_scaffold(args):
    """Scaffold generator"""
    name, *cmd_args = args
    scaffold.generate(name, cmd_args)


@generate.command('resource')
@click.argument('args', nargs=-1)
def generate_resource(args):
    """Resource generator"""
    name, *cmd_args = args
    resource.generate(name, cmd_args)


@generate.command('authentication')
def generate_authentication():
    """Authentication generator"""
    authentication.generate()
