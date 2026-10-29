"""Reflect only in the explicit schema-dump task; atomically publish its artifact."""

import ast
import os
import stat
import tempfile
import textwrap
from pathlib import Path

import click
import sqlalchemy as sa
from alembic.autogenerate import render_python_code
from alembic.migration import MigrationContext
from alembic.operations import ops
from flask import current_app
from flask.cli import with_appcontext

from flaskteroids.cli.output import status


def snapshot_source(connection):
    metadata = sa.MetaData()
    metadata.reflect(connection)
    operations = []
    for table in sorted(metadata.tables.values(), key=lambda table: table.key):
        if table.name == "alembic_version":
            continue
        for column in table.columns:
            if isinstance(column.type, sa.types.NullType):
                raise click.ClickException(
                    f"Cannot snapshot unknown database type for {table.name}.{column.name}."
                )
        operations.append(ops.CreateTableOp.from_table(table))
        operations.extend(
            ops.CreateIndexOp.from_index(index)
            for index in sorted(table.indexes, key=lambda index: index.name or "")
        )
    rendered = render_python_code(
        ops.UpgradeOps(operations),
        alembic_module_prefix="snapshot.",
        migration_context=MigrationContext.configure(connection),
    )
    body = textwrap.dedent(
        "\n".join(
            line for line in rendered.splitlines() if not line.lstrip().startswith("#")
        )
    )
    # Alembic's public renderer references dialect namespaces for native types.
    names = {
        node.id for node in ast.walk(ast.parse(body)) if isinstance(node, ast.Name)
    }
    dialects = sorted(names & {"postgresql", "mysql", "sqlite", "mssql", "oracle"})
    imports = "import sqlalchemy as sa\n"
    if dialects:
        imports += f"from sqlalchemy.dialects import {', '.join(dialects)}\n"
    return (
        '# Generated from the database. Do not edit; run "flask db:schema:dump".\n'
        + imports
        + "from flaskteroids.schema import Snapshot\n\n"
        + "snapshot = Snapshot()\nmetadata = snapshot.metadata\n\n"
        + body
        + "\n"
    )


def dump_schema(application=None):
    application = application or current_app
    path = Path(application.project_root) / "db/schema.py"
    if not path.resolve().is_relative_to(Path(application.project_root).resolve()):
        raise click.ClickException(
            "The schema snapshot must be inside the application project root."
        )
    engine = application.extensions["flaskteroids.db"].engine
    with engine.connect() as connection:
        source = snapshot_source(connection)
    compile(source, str(path), "exec")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(source)
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


@click.command("db:schema:dump")
@with_appcontext
def dump():
    """Refresh the database schema snapshot.

    Regenerate db/schema.py from the selected database without changing data.
    Application initialization runs normally; no model mappings are required.

    \b
    Example:
      flask db:schema:dump
    """
    path = dump_schema()
    status("write", path.relative_to(current_app.project_root))
