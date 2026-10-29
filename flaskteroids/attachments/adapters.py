"""Discover storage provider classes without importing unselected providers."""

from importlib.metadata import entry_points
from inspect import isabstract

from flaskteroids.attachments.services import DiskService
from flaskteroids.storage import StorageError, StorageService


def build_service(adapter, project_root, **options):
    if not isinstance(adapter, str) or not adapter:
        raise StorageError("Storage configuration requires a service name")
    providers = {"Disk": DiskService}
    for entry in entry_points(group="flaskteroids.storage"):
        if entry.name in providers:
            raise StorageError(f"Duplicate storage adapter {entry.name!r}")
        providers[entry.name] = entry
    provider = providers.get(adapter)
    if provider is None:
        raise StorageError(
            f"Unknown storage adapter {adapter!r}. Install the provider package "
            f"registering {adapter!r} in flaskteroids.storage."
        )
    if adapter != "Disk":
        try:
            provider = provider.load()
        except ImportError as error:
            raise StorageError(
                f"Cannot load storage adapter {adapter!r}; check its dependencies"
            ) from error
    if (
        not isinstance(provider, type)
        or not issubclass(provider, StorageService)
        or isabstract(provider)
    ):
        raise StorageError(
            f"Storage adapter {adapter!r} must be a concrete StorageService class"
        )
    service = provider.from_config(project_root, **options)
    if not isinstance(service, StorageService):
        raise StorageError(f"Storage adapter {adapter!r} returned an invalid service")
    return service
