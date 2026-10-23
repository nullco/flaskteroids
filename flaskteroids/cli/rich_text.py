import re
from datetime import datetime
from importlib.resources import files
from pathlib import Path

import click
from alembic import command
from alembic.operations import ops
from alembic.script import ScriptDirectory
from flask import current_app
from flask.cli import with_appcontext

from flaskteroids.cli.attachments import install as attachments_install
from flaskteroids.cli.db.config import get_config
from flaskteroids.rich_text.encryption import generate_encryption_key
from flaskteroids.rich_text.schema import metadata


@click.command("rich_text:keys")
def encryption_init():
    """Generate a dedicated rich-text encryption key.

    Prints secret YAML for flask credentials:edit. Do not commit or log the
    plaintext output. Existing keys and credentials are never overwritten.
    """
    click.echo(f"rich_text:\n  encryption_key: {generate_encryption_key()}")


@click.command("rich_text:install")
@click.option(
    "--force",
    is_flag=True,
    help="Replace existing editor assets; review local customizations first.",
)
@with_appcontext
def install(force):
    """Install rich-text storage and the Trix editor.

    Run flask db:migrate afterward to create the shared rich_texts table.
    Preserves existing assets and layout content. Repeated runs do not generate
    duplicate migrations. Also installs attachment storage for embedded files.
    Use --force to update application-owned editor assets after a framework upgrade.
    """
    config = get_config()
    if not Path(config.config_file_name).is_file():
        raise click.ClickException("Initialize migrations first with flask db:init")
    click.get_current_context().invoke(attachments_install)
    root = current_app.project_root
    source = root / current_app.config.assets.source_path / "rich_text"
    source.mkdir(parents=True, exist_ok=True)
    resources = files("flaskteroids.rich_text").joinpath("assets")
    for name in (
        "trix.js",
        "trix.css",
        "rich_text.js",
        "rich_text.css",
        "TRIX-LICENSE",
        "DOMPURIFY-LICENSE",
        "README.md",
    ):
        target = source / name
        if force or not target.exists():
            target.write_bytes(resources.joinpath(name).read_bytes())
            click.echo(f"    create  {target.relative_to(root)}")

    layout = root / current_app.config.paths.views / "layouts/application.html"
    if layout.exists():
        text = layout.read_text()
        if not re.search(r"\brich_text_assets\s*\(", text):
            updated, count = re.subn(
                r"</head\s*>",
                "    {{ rich_text_assets() }}\n  </head>",
                text,
                count=1,
                flags=re.I,
            )
            if count:
                layout.write_text(updated)
                click.echo(f"    modify  {layout.relative_to(root)}")
            else:
                click.echo("Add {{ rich_text_assets() }} to your layout's head.")
    else:
        click.echo("Add {{ rich_text_assets() }} to your layout's head.")

    scripts = ScriptDirectory.from_config(config)
    message = "create rich text table"
    if any(revision.doc == message for revision in scripts.walk_revisions()):
        click.echo("Rich-text migration already exists.")
        return

    def directives(context, revision, entries):
        script = entries[0]
        for table in metadata.sorted_tables:
            script.upgrade_ops.ops.append(ops.CreateTableOp.from_table(table))
            for index in sorted(table.indexes, key=lambda index: index.name):
                script.upgrade_ops.ops.append(ops.CreateIndexOp.from_index(index))
        script.downgrade_ops.ops.extend(
            ops.DropTableOp(table.name) for table in reversed(metadata.sorted_tables)
        )

    command.revision(
        config,
        message=message,
        rev_id=datetime.now().strftime("%Y%m%d%H%M%S%f"),
        process_revision_directives=directives,
    )
    click.echo("Run flask db:migrate to create the rich-text table.")
