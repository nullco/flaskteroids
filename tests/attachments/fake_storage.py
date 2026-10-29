"""A provider-neutral storage implementation for attachment workflow tests."""

import io

from flaskteroids.storage import (
    StorageService,
    validate_key,
    validate_range,
    verify_checksum,
)


class MemoryService(StorageService):
    def __init__(self, *, public=False, **options):
        super().__init__(public=public)
        self.options = options
        self.files = {}
        self.uploads = []
        self.ranges = []
        self.bodies = []
        self.stream_class = io.BytesIO

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
        validate_key(key)
        if checksum is not None:
            verify_checksum(data, checksum)
        self.files[key] = data if isinstance(data, bytes) else data.read()
        self.uploads.append(
            {
                "key": key,
                "checksum": checksum,
                "content_type": content_type,
                "filename": filename,
                "disposition": disposition,
            }
        )

    def open(self, key, *, start=None, end=None):
        validate_key(key)
        validate_range(start, end)
        self.ranges.append((start, end))
        if key not in self.files:
            raise FileNotFoundError(key)
        data = self.files[key][start or 0 : None if end is None else end + 1]
        body = self.stream_class(data)
        self.bodies.append(body)
        return body

    def delete(self, key):
        validate_key(key)
        self.files.pop(key, None)

    def exist(self, key):
        validate_key(key)
        return key in self.files

    def url(self, key, *, expires_in, filename, content_type, disposition):
        validate_key(key)
        return f"https://storage.example/{key}"
