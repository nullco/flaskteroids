"""Consistent status lines for human-facing command progress."""

import click


def format_status(action, message):
    return f"{action:>10}  {message}"


def status(action, message):
    click.echo(format_status(action, message))
