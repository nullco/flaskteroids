from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

from flask import current_app, redirect
from werkzeug.local import LocalProxy

from flaskteroids.actions import params
from flaskteroids.application import Application
from flaskteroids.flash import flash
from flaskteroids.rules import rules

application = LocalProxy(lambda: current_app)


try:
    __version__ = _version("flaskteroids")
except PackageNotFoundError:
    # This means that package is not installed
    __version__ = None


def redirect_to(target, **kwargs):
    notice = kwargs.pop("notice", None)
    if notice:
        flash["notice"] = notice
    alert = kwargs.pop("alert", None)
    if alert:
        flash["alert"] = alert
    status = kwargs.get("status") or 302
    return redirect(target, code=status)


__all__ = [
    "Application",
    "application",
    "flash",
    "params",
    "redirect_to",
    "rules",
]
