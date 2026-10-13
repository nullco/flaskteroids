import base64
import hashlib
import io

import pytest

from flaskteroids.attachments.services import (
    DiskService,
    IntegrityError,
    S3Service,
    StorageError,
)

KEY = "a" * 28
DATA = b"file contents"
CHECKSUM = base64.b64encode(hashlib.md5(DATA, usedforsecurity=False).digest()).decode()


def test_disk_service_upload_download_and_delete(tmp_path):
    service = DiskService(tmp_path)
    assert not service.exist(KEY)
    service.upload(KEY, DATA, checksum=CHECKSUM, content_type="text/plain")
    assert service.exist(KEY)
    assert service.download(KEY) == DATA
    assert service.path_for(KEY) == tmp_path / "aa" / "aa" / KEY
    service.delete(KEY)
    service.delete(KEY)
    assert not service.exist(KEY)


@pytest.mark.parametrize(
    "key", ["../secret", "/etc/passwd", "short", "a" * 27 + "/", "\x00"]
)
def test_disk_rejects_invalid_keys(tmp_path, key):
    with pytest.raises(StorageError):
        DiskService(tmp_path).path_for(key)


def test_disk_rejects_paths_that_escape_root_through_symlinks(tmp_path):
    root = tmp_path / "storage"
    root.mkdir()
    (root / "aa").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(StorageError):
        DiskService(root).path_for(KEY)


def test_bad_checksum_does_not_write_a_file(tmp_path):
    service = DiskService(tmp_path)
    with pytest.raises(IntegrityError):
        service.upload(KEY, DATA, checksum="incorrect", content_type="text/plain")
    assert not service.exist(KEY)


def test_s3_upload_download_and_idempotent_delete(mocker):
    client = mocker.Mock()
    client.get_object.return_value = {"Body": io.BytesIO(DATA)}
    service = S3Service(bucket="uploads", client=client)
    service.upload(KEY, DATA, checksum=CHECKSUM, content_type="text/plain")
    client.put_object.assert_called_once_with(
        Bucket="uploads",
        Key=KEY,
        Body=DATA,
        ContentMD5=CHECKSUM,
        ContentType="text/plain",
    )
    assert service.download(KEY) == DATA
    service.delete(KEY)
    client.delete_object.assert_called_once_with(Bucket="uploads", Key=KEY)


def test_s3_rejects_bad_checksum_and_keys_before_contacting_service(mocker):
    client = mocker.Mock()
    service = S3Service(bucket="uploads", client=client)
    with pytest.raises(IntegrityError):
        service.upload(KEY, DATA, checksum="incorrect", content_type="text/plain")
    with pytest.raises(StorageError):
        service.delete("../secret")
    client.put_object.assert_not_called()
    client.delete_object.assert_not_called()


def test_s3_rails_configuration_maps_to_sdk_options(mocker):
    pytest.importorskip("boto3")
    client = mocker.patch("boto3.client")
    S3Service(
        bucket="uploads",
        region="test-region",
        endpoint="https://s3.example.com",
        access_key_id="key",
        secret_access_key="secret",
        force_path_style=True,
    )
    assert client.call_args.args == ("s3",)
    options = client.call_args.kwargs
    assert options["region_name"] == "test-region"
    assert options["aws_access_key_id"] == "key"
    assert options["aws_secret_access_key"] == "secret"
    assert options["endpoint_url"] == "https://s3.example.com"
    assert options["config"].s3["addressing_style"] == "path"


def test_s3_existence_does_not_hide_permission_errors(mocker):
    exceptions = pytest.importorskip("botocore.exceptions")
    client = mocker.Mock()
    service = S3Service(bucket="uploads", client=client)
    client.head_object.side_effect = exceptions.ClientError(
        {"Error": {"Code": "404"}}, "HeadObject"
    )
    assert not service.exist(KEY)
    client.head_object.side_effect = exceptions.ClientError(
        {"Error": {"Code": "AccessDenied"}}, "HeadObject"
    )
    with pytest.raises(exceptions.ClientError):
        service.exist(KEY)
