import pytest

from flaskteroids.attachments.services import DiskService
from flaskteroids.testing import StorageServiceContract
from tests.attachments.fake_storage import MemoryService


class TestDiskService(StorageServiceContract):
    @pytest.fixture
    def storage_service(self, app, tmp_path):
        service = DiskService(tmp_path / "contract")
        service.name = "test"
        with app.test_request_context():
            yield service


class TestMemoryService(StorageServiceContract):
    @pytest.fixture
    def storage_service(self):
        return MemoryService()


@pytest.mark.parametrize("failure", [None, "read", "callback"])
def test_download_closes_streams_on_success_and_failure(mocker, failure):
    service = MemoryService()
    stream = mocker.Mock()
    stream.read.side_effect = (
        RuntimeError("read failed") if failure == "read" else [b"contents", b""]
    )
    mocker.patch.object(service, "open", return_value=stream)
    callback = mocker.Mock(
        side_effect=RuntimeError("callback failed") if failure == "callback" else None
    )
    if failure:
        with pytest.raises(RuntimeError, match=f"{failure} failed"):
            service.download("a" * 28, callback)
    else:
        service.download("a" * 28, callback)
    stream.close.assert_called_once()
