import re
from datetime import datetime
from pathlib import Path

import click
from alembic import command
from alembic.operations import ops
from alembic.script import ScriptDirectory
from flask import current_app
from flask.cli import with_appcontext

from flaskteroids.cli.attachments import install as attachments_install
from flaskteroids.cli.db.config import get_config
from flaskteroids.cli.db.output import migration_output, report_revision
from flaskteroids.cli.output import status
from flaskteroids.rich_text.installation import install_javascript
from flaskteroids.rich_text.schema import metadata


@click.command("rich_text:install")
@with_appcontext
def install():
    """Install rich-text storage and the Lexxy editor.

    Run flask db:migrate afterward to create the shared rich_texts table.
    Preserves application code and layout content. Repeated runs do not generate
    duplicate migrations. Also installs attachment storage for embedded files.
    """
    config = get_config()
    if not Path(config.config_file_name).is_file():
        raise click.ClickException("Initialize migrations first with flask db:init")
    click.get_current_context().invoke(attachments_install)
    root = current_app.project_root
    result = install_javascript(root, views_path=current_app.config.paths.views)
    for path in result.files:
        status("write", path.relative_to(root))
    for instruction in result.instructions:
        status("next", instruction)

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
                status("modify", layout.relative_to(root))
            else:
                status("next", "Add {{ rich_text_assets() }} to your layout's head.")
    else:
        status("next", "Add {{ rich_text_assets() }} to your layout's head.")

    scripts = ScriptDirectory.from_config(config)
    message = "create rich text table"
    if any(revision.doc == message for revision in scripts.walk_revisions()):
        status("skip", "Rich-text migration already exists.")
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

    with migration_output():
        revision = command.revision(
            config,
            message=message,
            rev_id=datetime.now().strftime("%Y%m%d%H%M%S%f"),
            process_revision_directives=directives,
        )
    report_revision(revision, root)
    status("next", "Run flask db:migrate to create the rich-text table.")
