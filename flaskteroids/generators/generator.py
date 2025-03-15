import click
from flask.cli import AppGroup

cli = AppGroup('steroids:generate')


@cli.command('migration')
@click.argument('args', nargs=-1)
def generate_migration(args):
    cmd, *cmd_args = args
    print(f'Generating migration... with {args}')
