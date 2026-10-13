import io
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from flask import current_app
from werkzeug.datastructures import FileStorage


def fixture_file_upload(path, content_type=None):
    path = Path(path)
    if not path.is_absolute():
        path = current_app.project_root / "test" / "fixtures" / "files" / path
    return FileStorage(
        stream=io.BytesIO(path.read_bytes()),
        filename=path.name,
        content_type=content_type,
    )


@contextmanager
def temporary_storage(application):
    storage = application.extensions["flaskteroids.attachments"]
    configurations, services = storage.configurations, storage.services
    with TemporaryDirectory(prefix="flaskteroids-storage-") as root:
        storage.configurations = {
            name: {"service": "Disk", "root": str(Path(root, name))}
            for name in configurations
        }
        storage.services = {}
        try:
            yield storage
        finally:
            storage.configurations, storage.services = configurations, services
