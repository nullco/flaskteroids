import click

from flaskteroids.cli.importmap import install as importmap_install


@click.command("turbo:install", short_help="Configure the local Turbo module.")
@click.pass_context
def install(ctx):
    """Configure the framework-provided Turbo runtime through import maps.

    Preserves application code and custom layouts. Existing views can opt into
    minimal frame layouts with {% extends layout %}.
    """
    ctx.invoke(importmap_install)
