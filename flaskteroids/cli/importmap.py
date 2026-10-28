"""Thin command adapters for bootless import-map package operations."""

import json
from pathlib import Path

import click
from flask import current_app
from flask.cli import with_appcontext
from werkzeug.routing import Map, Rule

from flaskteroids._assets.paths import url_prefix
from flaskteroids.assets import OUTPUT_PATH, SOURCE_PATH, AssetPipeline
from flaskteroids.importmaps.installation import install as install_application
from flaskteroids.importmaps.map import ImportMap
from flaskteroids.importmaps.packages import PROVIDERS, Packager


class ImportmapCommands(click.Group):
    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except (ValueError, OSError, SyntaxError) as error:
            raise click.ClickException(str(error)) from error


@click.group(cls=ImportmapCommands, short_help="Manage pinned JavaScript modules.")
@click.option("--root", type=click.Path(path_type=Path, file_okay=False), default=".")
@click.pass_context
def importmap(ctx, root):
    """Pin and vendor browser modules without booting the application."""
    ctx.obj = root.resolve()


def _report(pins):
    for pin in pins:
        click.echo(f'Pinned "{pin.name}" to vendor/javascript/{pin.filename}')


@importmap.command(short_help="Resolve and download packages.")
@click.argument("packages", nargs=-1, required=True)
@click.option("--from", "provider", type=click.Choice(tuple(PROVIDERS)), default="jspm")
@click.option(
    "--env", default="production", type=click.Choice(["production", "development"])
)
@click.option("--preload/--no-preload", default=None)
@click.pass_obj
def pin(root, packages, provider, env, preload):
    """Resolve and download PACKAGES, including returned dependencies."""
    _report(
        Packager(root).pin(
            *packages, provider=provider, environment=env, preload=preload
        )
    )


@importmap.command(short_help="Remove named pins and owned downloads.")
@click.argument("packages", nargs=-1, required=True)
@click.pass_obj
def unpin(root, packages):
    """Remove named pins and their owned downloads; retain shared dependencies."""
    for name in Packager(root).unpin(*packages):
        click.echo(f'Unpinned "{name}"')


@importmap.command(short_help="Restore downloaded package versions.")
@click.option("--from", "provider", type=click.Choice(tuple(PROVIDERS)), default="jspm")
@click.pass_obj
def pristine(root, provider):
    """Redownload managed pins at their recorded versions."""
    _report(Packager(root).pristine(provider=provider))


@importmap.command(short_help="Update downloaded package pins.")
@click.option("--from", "provider", type=click.Choice(tuple(PROVIDERS)), default="jspm")
@click.pass_obj
def update(root, provider):
    """Resolve current versions of managed pins, preserving pin options."""
    _report(Packager(root).update(provider=provider))


@importmap.command(short_help="List downloaded package versions.")
@click.pass_obj
def packages(root):
    """List downloaded package names and recorded versions."""
    for package in Packager(root).packages():
        click.echo(f"{package.name} {package.version or 'unknown'}")


@importmap.command("json", short_help="Show the resolved import map.")
@click.option(
    "--environment",
    default="development",
    envvar="FLASKTEROIDS_ENV",
)
@click.option("--source", default=SOURCE_PATH)
@click.option("--output", default=OUTPUT_PATH)
@click.option("--prefix", default="/assets")
@click.pass_obj
def show_json(root, environment, source, output, prefix):
    """Print the resolved browser map without loading credentials or a database."""
    pipeline = AssetPipeline(root, source_path=source, output_path=output)
    compiled = environment not in ("development", "test")
    prefix = url_prefix(prefix).rstrip("/")
    urls = Map([Rule(f"{prefix}/<path:filename>", endpoint="static")]).bind("")

    def resolver(name):
        filename = (
            pipeline.compiled_name(name) if compiled else pipeline.source_name(name)
        )
        return urls.build("static", {"filename": filename})

    def integrity(name):
        return pipeline.asset_integrity(name, compiled=compiled)

    resolved = ImportMap.load(root).resolve(resolver, integrity_resolver=integrity)
    click.echo(json.dumps(resolved.to_dict(), indent=2))


@click.command("importmap:install", short_help="Install the import-map workflow.")
@with_appcontext
def install():
    """Install config/importmap.py, bin/importmap, and the module entrypoint."""
    result = install_application(
        current_app.project_root, views_path=current_app.config.paths.views
    )
    for path in result.files:
        click.echo(f"    write  {path.relative_to(current_app.project_root)}")
    for instruction in result.instructions:
        click.echo(instruction)
