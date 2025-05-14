from flaskteroids.controller import params, redirect_to
from importlib.metadata import PackageNotFoundError, version as _version


try:
    __version__ = _version("flaskteroids")
except PackageNotFoundError:
    # This means that package is not installed
    __version__ = None

__all__ = [
    'params',
    'redirect_to'
]
