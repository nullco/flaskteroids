import os
import click
from pathlib import Path


@click.group()
def cli():
    pass


@cli.command('new')
@click.argument('app_name')
def new(app_name):
    base_path = os.path.abspath(app_name)
    structure = [
        "app/models/",
        "app/views/",
        "app/controllers/",
        "config/"
    ]
    try:
        os.makedirs(base_path, exist_ok=True)
        for entry in structure:
            _resolve(os.path.join(base_path, entry))

        click.echo(f"App structure created at: {base_path}")
    except Exception as e:
        click.echo(f"Error creating structure: {e}")


def _resolve(entry: str):
    if entry.endswith('.py'):
        Path(entry).touch(exist_ok=True)
    else:
        os.makedirs(entry, exist_ok=True)
