from flask import g


class CurrentMeta(type):
    def __getattr__(cls, name):
        if name not in g:
            return None
        return g.name

    def __setattr__(cls, name, value):
        setattr(g, name, value)


class Current(metaclass=CurrentMeta):
    pass
