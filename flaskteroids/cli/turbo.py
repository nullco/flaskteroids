import re

import click
from flask import current_app
from flask.cli import with_appcontext

from flaskteroids.turbo.installation import SCRIPT_TAG, install_assets

_ORIGINAL_CDN = re.compile(
    r"https://cdn\.jsdelivr\.net/npm/@hotwired/turbo@(?:latest|[\d.]+)/dist/"
    r"turbo\.es2017-esm\.min\.js"
)
_LOCAL_RUNTIME = re.compile(r"asset_path\(\s*['\"]turbo/turbo\.js['\"]\s*\)")


@click.command("turbo:install")
@click.option(
    "--force",
    is_flag=True,
    help="Replace app-owned Turbo assets; review customizations first.",
)
@with_appcontext
def install(force):
    """Install the locally bundled Turbo runtime.

    Preserves app-owned assets unless --force is supplied. Migrates the original
    generated CDN URL; custom layouts receive instructions instead. Existing
    views can opt into minimal frame layouts with {% extends layout %}.
    """
    root = current_app.project_root
    for target in install_assets(
        root, source_path=current_app.config.assets.source_path, force=force
    ):
        click.echo(f"    create  {target.relative_to(root)}")
    layout = root / current_app.config.paths.views / "layouts/application.html"
    text = layout.read_text() if layout.exists() else ""
    updated = _ORIGINAL_CDN.sub("{{ asset_path('turbo/turbo.js') }}", text)
    if _LOCAL_RUNTIME.search(updated):
        if not re.search(r"name\s*=\s*['\"]csrf-token['\"]", updated, flags=re.I):
            updated = re.sub(
                r"</head\s*>",
                '    <meta name="csrf-token" content="{{ csrf_token() }}">\n  </head>',
                updated,
                count=1,
                flags=re.I,
            )
        if updated != text:
            layout.write_text(updated)
            click.echo(f"    modify  {layout.relative_to(root)}")
    else:
        click.echo("Load exactly one Turbo runtime in your application layout:")
        click.echo(SCRIPT_TAG)
        click.echo('Also add <meta name="csrf-token" content="{{ csrf_token() }}">.')
    click.echo("Use {% extends layout %} in page views for minimal frame responses.")
