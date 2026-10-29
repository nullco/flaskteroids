import pytest

from flaskteroids.attachments.services import DiskService
from flaskteroids.storage import StorageError

KEY = "a" * 28


def test_disk_service_shards_keys_below_its_root(tmp_path):
    service = DiskService(tmp_path)
    assert service.path_for(KEY) == tmp_path / "aa" / "aa" / KEY
    assert service.local_path(KEY) == service.path_for(KEY)


@pytest.mark.parametrize(
    "key", ["../secret", "/etc/passwd", "short", "a" * 27 + "/", "\x00"]
)
def test_disk_rejects_invalid_paths(tmp_path, key):
    with pytest.raises(StorageError):
        DiskService(tmp_path).path_for(key)


def test_disk_rejects_paths_that_escape_root_through_symlinks(tmp_path):
    root = tmp_path / "storage"
    root.mkdir()
    (root / "aa").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(StorageError):
        DiskService(root).path_for(KEY)
