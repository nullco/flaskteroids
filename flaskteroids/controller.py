from functools import wraps
from flask import redirect, render_template
from flaskteroids.actions import invoke_action, ParamsProxy
from flaskteroids.exceptions import Redirect
import flaskteroids.registry as registry


class ActionController:

    def __getattribute__(self, name: str):
        if name.startswith('_'):
            return super().__getattribute__(name)

        ns = registry.get(self.__class__)
        if 'actions' not in ns or name not in ns['actions']:
            return super().__getattribute__(name)

        action = invoke_action(self, super().__getattribute__(name))

        @wraps(action)
        def wrapper(*args, **kwargs):
            res = action(*args, **kwargs)
            if res:
                return res
            cname = self.__class__.__name__.replace("Controller", "").lower()
            view_template = render_template(f'{cname}/{name}.html', **self.__dict__)
            return view_template
        return wrapper


params = ParamsProxy()


def redirect_to(url):
    raise Redirect(redirect(url))
