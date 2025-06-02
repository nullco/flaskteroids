from werkzeug.local import LocalProxy
from flask import g


class Current():
    def __init__(self):
        self._data = {}

    def __getattr__(self, name):
        return self._data.get(name)

    def __setattr__(self, name, value):
        if name in '_data':
            return super().__setattr__(name, value)
        self._data[name] = value


def _get_current():
    if 'current' not in g:
        g.current = Current()
    return g.current


current = LocalProxy(_get_current)
