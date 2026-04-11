from flask import redirect
from cucurbit.actions import params
from cucurbit.flash import flash
from cucurbit.rules import rules
from importlib.metadata import PackageNotFoundError, version as _version


try:
    __version__ = _version("cucurbit")
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
    status = kwargs.get('status') or 302
    return redirect(target, code=status)


__all__ = [
    'params',
    'flash',
    'rules',
    'redirect_to'
]
