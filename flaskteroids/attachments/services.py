import io
import shutil
from pathlib import Path

from flask import url_for

from flaskteroids.attachments.signatures import signed_token
from flaskteroids.storage import (
    IntegrityError,
    StorageError,
    StorageService,
    validate_key,
    validate_range,
    verify_checksum,
)


class _RangeStream:
    def __init__(self, stream, remaining):
        self.stream = stream
        self.remaining = remaining

    def read(self, size=-1):
        if self.remaining is not None:
            size = self.remaining if size < 0 else min(size, self.remaining)
        data = self.stream.read(size)
        if self.remaining is not None:
            self.remaining -= len(data)
        return data

    def close(self):
        self.stream.close()


class DiskService(StorageService):
    def __init__(self, root, *, public=False):
        self.root = Path(root).resolve()
        super().__init__(public=public)

    @classmethod
    def from_config(cls, project_root, **options):
        return cls(**(options | {"root": project_root / Path(options["root"])}))

    def local_path(self, key):
        return self.path_for(key)

    def path_for(self, key):
        validate_key(key)
        path = self.root / key[:2] / key[2:4] / key
        if not path.resolve().is_relative_to(self.root):
            raise StorageError("Storage path escapes its root")
        return path

    def upload(
        self,
        key,
        data,
        *,
        checksum=None,
        content_type=None,
        filename=None,
        disposition=None,
    ):
        stream = io.BytesIO(data) if isinstance(data, bytes) else data
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as destination:
            shutil.copyfileobj(stream, destination)
        if checksum is not None:
            try:
                with path.open("rb") as stored:
                    verify_checksum(stored, checksum)
            except IntegrityError:
                self.delete(key)
                raise

    def open(self, key, *, start=None, end=None):
        validate_range(start, end)
        stream = self.path_for(key).open("rb")
        stream.seek(start or 0)
        remaining = None if end is None else end - (start or 0) + 1
        return _RangeStream(stream, remaining)

    def delete(self, key):
        self.path_for(key).unlink(missing_ok=True)

    def exist(self, key):
        return self.path_for(key).is_file()

    def url(self, key, *, expires_in, filename, content_type, disposition):
        validate_key(key)
        token = signed_token(
            "blob_key",
            {
                "key": key,
                "service_name": self.name,
                "filename": filename,
                "content_type": content_type,
                "disposition": disposition,
            },
            None if self.public else expires_in,
        )
        return url_for(
            "flaskteroids_attachments.disk",
            encoded_key=token,
            filename=filename,
            _external=True,
        )
