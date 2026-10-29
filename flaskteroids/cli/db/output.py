"""Adapt Alembic's artifact progress to the framework's command output."""

import os
from contextlib import contextmanager, redirect_stdout
from io import StringIO

from flaskteroids.cli.output import status


@contextmanager
def migration_output():
    # Alembic writes progress directly to stdout rather than Config.stdout.
    # Exceptions and stderr diagnostics remain available to the caller.
    with redirect_stdout(StringIO()):
        yield


def report_revision(revision, root):
    revisions = revision if isinstance(revision, list) else [revision]
    for script in revisions:
        if script is not None:
            status("create", os.path.relpath(script.path, root))
