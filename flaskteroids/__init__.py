from collections.abc import Mapping
from flask import g


class Params(Mapping):

    def __getitem__(self, key):
        self._ensure_params()
        return g.params.get(key)

    def __setitem__(self, key, val):
        self._ensure_params()
        g.params[key] = val

    def __iter__(self):
        self._ensure_params()
        return iter(g.params)

    def __len__(self):
        self._ensure_params()
        return len(g.params)

    def items(self):
        self._ensure_params()
        return g.params.items()

    def update(self, values):
        self._ensure_params()
        g.params.update(values)

    def _ensure_params(self):
        if not hasattr(g, 'params'):
            g.params = {}

    def __str__(self) -> str:
        self._ensure_params()
        return str(g.params)


params = Params()
