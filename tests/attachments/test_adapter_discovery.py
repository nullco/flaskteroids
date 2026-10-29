from importlib.metadata import EntryPoint

import pytest

from flaskteroids.storage import StorageError
from tests.attachments.fake_storage import MemoryService


def provider(name="Memory", value="tests.attachments.fake_storage:MemoryService"):
    return EntryPoint(name=name, value=value, group="flaskteroids.storage")


def test_configured_provider_is_discovered_and_cached(storage, memory_provider):
    storage.configurations["remote"] = {"service": "Memory", "public": True}
    service = storage.service("remote")
    assert isinstance(service, MemoryService)
    assert service.name == "remote"
    assert service.public
    assert storage.service("remote") is service


def test_service_configurations_receive_independent_instances(storage, memory_provider):
    storage.configurations.update(
        first={"service": "Memory"}, second={"service": "Memory"}
    )
    first, second = storage.service("first"), storage.service("second")
    assert first is not second
    assert (first.name, second.name) == ("first", "second")


def test_provider_instances_are_scoped_to_the_application(
    app, storage, memory_provider
):
    other = type(app).initialize(environment="test", root_path=app.project_root)
    try:
        second = other.extensions["flaskteroids.attachments"]
        for extension in (storage, second):
            extension.configurations["remote"] = {"service": "Memory"}
        assert storage.service("remote") is not second.service("remote")
    finally:
        other.extensions["flaskteroids.db"].engine.dispose()


def test_unselected_providers_are_not_imported(storage, mocker):
    mocker.patch(
        "flaskteroids.attachments.adapters.entry_points",
        return_value=[provider(), provider("Unavailable", "missing_provider:Service")],
    )
    storage.configurations["remote"] = {"service": "Memory"}
    assert isinstance(storage.service("remote"), MemoryService)


@pytest.mark.parametrize("name", ["Memory", "Disk"])
def test_duplicate_provider_names_are_rejected(storage, mocker, name):
    entries = [provider(name)]
    if name == "Memory":
        entries.append(provider(name))
    mocker.patch("flaskteroids.attachments.adapters.entry_points", return_value=entries)
    storage.configurations["remote"] = {"service": name}
    with pytest.raises(StorageError, match="Duplicate storage adapter"):
        storage.service("remote")


def test_missing_provider_reports_installation_requirement(storage, mocker):
    mocker.patch("flaskteroids.attachments.adapters.entry_points", return_value=[])
    storage.configurations["remote"] = {"service": "Unavailable"}
    with pytest.raises(StorageError, match="Install the provider package"):
        storage.service("remote")


@pytest.mark.parametrize(
    "value, message",
    [
        ("missing_provider:Service", "Cannot load storage adapter"),
        ("builtins:dict", "concrete StorageService"),
        ("flaskteroids.storage:StorageService", "concrete StorageService"),
    ],
)
def test_invalid_provider_fails_with_a_configuration_error(
    storage, mocker, value, message
):
    mocker.patch(
        "flaskteroids.attachments.adapters.entry_points",
        return_value=[provider(value=value)],
    )
    storage.configurations["remote"] = {"service": "Memory"}
    with pytest.raises(StorageError, match=message):
        storage.service("remote")
    assert "remote" not in storage.services


@pytest.mark.parametrize("adapter", [None, "", 42])
def test_storage_configuration_requires_an_adapter_name(storage, adapter):
    storage.configurations["remote"] = {"service": adapter}
    with pytest.raises(StorageError, match="requires a service name"):
        storage.service("remote")
