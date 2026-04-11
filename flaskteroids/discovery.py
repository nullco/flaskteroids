import logging
import pkgutil
import inspect
from importlib import import_module


_logger = logging.getLogger(__name__)


def discover_classes(module_name, cls, ignore=None):
    try:
        package = import_module(module_name)
    except ModuleNotFoundError:
        _logger.debug(f'No {module_name} module detected... ignoring')
        return {}
    package_path = package.__path__
    entries = {}
    for _, submodule_name, _ in pkgutil.iter_modules(package_path):
        absolute_name = f"{module_name}.{submodule_name}"
        module = import_module(absolute_name)
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, cls) and obj is not cls and (not ignore or name not in ignore):
                entries[name] = obj
    _logger.debug(f'discovered {len(entries)} classes in {module_name}')
    return entries


def discover_methods(cls, ignore=None):
    return [
        name for name, member in inspect.getmembers(cls)
        if inspect.isfunction(member) and not name.startswith('_')
        and (not ignore or name not in ignore)
    ]
