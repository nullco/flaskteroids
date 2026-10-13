from datetime import datetime
from pathlib import Path

import click
from alembic import command
from alembic.operations import ops
from alembic.script import ScriptDirectory
from flask import current_app
from flask.cli import with_appcontext

from flaskteroids.attachments.schema import metadata
from flaskteroids.cli.db.config import get_config

STORAGE_YAML = """test:
  service: Disk
  root: tmp/storage

local:
  service: Disk
  root: storage

# amazon:
#   service: S3
#   bucket: {env: S3_BUCKET}
#   region: {env: AWS_REGION}
#   access_key_id: {credential: aws.access_key_id}
#   secret_access_key: {credential: aws.secret_access_key}
"""


@click.command("attachments:install")
@with_appcontext
def install():
    """Generate the attachment tables migration.

    Requires flask db:init. Preserves existing config/storage.yml and does not
    apply migrations. Repeated runs do not generate duplicate migrations.
    Review the generated migration, then run flask db:migrate.

    \b
    Example:
      flask attachments:install
    """
    config = get_config()
    if not Path(config.config_file_name).is_file():
        raise click.ClickException("Initialize migrations first with flask db:init")
    scripts = ScriptDirectory.from_config(config)
    message = "create attachment tables"
    path = current_app.project_root / "config" / "storage.yml"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(STORAGE_YAML)
        click.echo("    create  config/storage.yml")
    if any(revision.doc == message for revision in scripts.walk_revisions()):
        click.echo("Attachment migration already exists.")
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
    click.echo("Run flask db:migrate to create the attachment tables.")
