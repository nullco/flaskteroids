import click
from flask import current_app
from flask.cli import with_appcontext


@click.command("middleware", short_help="Show the effective WSGI middleware stack.")
@with_appcontext
def middleware():
    """List middleware in incoming-request order, followed by Flask dispatch."""
    for entry in current_app.middleware:
        click.echo(f"use {entry.name}")
    click.echo("run flask.app.Flask.wsgi_app")
