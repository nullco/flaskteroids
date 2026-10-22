from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

from flask import current_app
from werkzeug.local import LocalProxy

from flaskteroids.application import Application
from flaskteroids.flash import flash
from flaskteroids.rules import declaration

application = LocalProxy(lambda: current_app)


try:
    __version__ = _version("flaskteroids")
except PackageNotFoundError:
    # This means that package is not installed
    __version__ = None


__all__ = [
    "Application",
    "application",
    "declaration",
    "flash",
]
