from flaskteroids.controller import params, redirect_to
from importlib.metadata import version as _version


__version__ = _version("flaskteroids")

__all__ = [
    'params',
    'redirect_to'
]
