from flask import redirect
from flaskteroids.actions import params
from flaskteroids.flash import flash
from flaskteroids.rules import rules
from importlib.metadata import PackageNotFoundError, version as _version


try:
    __version__ = _version("flaskteroids")
except PackageNotFoundError:
    # This means that package is not installed
    __version__ = None


def redirect_to(target, **kwargs):
    notice = kwargs.pop('notice', None)
    if notice:
        flash['notice'] = notice
    alert = kwargs.pop('alert', None)
    if alert:
        flash['alert'] = alert
    return redirect(target)


__all__ = [
    'params',
    'flash',
    'rules'
]
