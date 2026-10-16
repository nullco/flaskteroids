import io

import pytest
import yaml

from flaskteroids.attachments import Blob, StorageError
from flaskteroids.testing import fixture_file_upload, temporary_storage

pytestmark = pytest.mark.usefixtures("app_ctx")


def test_default_service_is_test_in_test_environment(storage, app):
    assert storage.service_name == "test"
    assert storage.service().root == app.project_root / "tmp/storage"


def test_blob_retains_its_service_when_default_changes(storage):
    blob = Blob.create_and_upload(io=io.BytesIO(b"file"), filename="file.txt")
    storage.service_name = "local"
    assert blob.service_name == "test"
    assert blob.download() == b"file"


def test_unknown_services_raise_a_configuration_error(storage):
    with pytest.raises(StorageError, match="was not found"):
        storage.service("missing")


def test_storage_resolves_credentials_and_environment_references(
    storage, app, monkeypatch, mocker
):
    storage.configurations["amazon"] = {
        "service": "S3",
        "bucket": {"env": "TEST_STORAGE_BUCKET"},
        "access_key_id": {"credential": "aws.access_key_id"},
        "secret_access_key": {"credential": "aws.secret_access_key"},
    }
    monkeypatch.setenv("TEST_STORAGE_BUCKET", "private-bucket")
    mocker.patch.object(
        app.credentials,
        "to_dict",
        return_value={
            "aws": {"access_key_id": "key", "secret_access_key": "secret"},
        },
    )
    service = mocker.patch("flaskteroids.attachments.extension.S3Service")
    storage.service("amazon")
    service.assert_called_once_with(
        bucket="private-bucket",
        access_key_id="key",
        secret_access_key="secret",
    )


def test_missing_environment_references_fail_closed(storage):
    storage.configurations["amazon"] = {
        "service": "S3",
        "bucket": {"env": "MISSING_BUCKET"},
    }
    with pytest.raises(StorageError, match="Missing storage environment variable"):
        storage.service("amazon")


def test_missing_credentials_fail_closed(storage, app, mocker):
    mocker.patch.object(app.credentials, "to_dict", return_value={})
    storage.configurations["amazon"] = {
        "service": "S3",
        "bucket": "bucket",
        "access_key_id": {"credential": "aws.key"},
    }
    with pytest.raises(StorageError, match="Missing storage credential"):
        storage.service("amazon")


def test_fixture_upload_and_temporary_storage_are_isolated(app, storage):
    path = app.project_root / "test/fixtures/files/report.txt"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"report")
    with temporary_storage(app):
        upload = fixture_file_upload("report.txt", "text/plain")
        assert upload.filename == "report.txt"
        assert upload.content_type == "text/plain"
        blob = Blob.create_and_upload(io=upload.stream, filename=upload.filename)
        disk_path = storage.service().path_for(blob.key)
        assert disk_path.is_file()
    assert not disk_path.exists()
    assert storage.service().root == app.project_root / "tmp/storage"


def test_temporary_storage_replaces_remote_services_without_contacting_them(
    app, storage
):
    storage.configurations["remote"] = {"service": "S3", "bucket": "private"}
    with temporary_storage(app):
        blob = Blob.create_and_upload(
            io=io.BytesIO(b"test"), filename="test.txt", service_name="remote"
        )
        assert blob.download() == b"test"


def test_yaml_configuration_is_loaded_on_application_boot(app, tmp_path):
    configuration = {"test": {"service": "Disk", "root": "custom/files"}}
    path = tmp_path / "config/storage.yml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(configuration))
    second = type(app).initialize(environment="test", root_path=tmp_path)
    extension = second.extensions["flaskteroids.attachments"]
    assert extension.service().root == tmp_path / "custom/files"
