from flask import redirect, render_template
from flaskteroids.actions import invoke_action, ParamsProxy
from flaskteroids.exceptions import Redirect


class ActionController:

    def __getattr__(self, name):
        if name.startswith('invoke_'):
            name = name.replace('invoke_', '')
            action = invoke_action(self, getattr(self, name))

            def wrapper(*args, **kwargs):
                res = action(*args, **kwargs)
                if res:
                    return res
                cname = self.__class__.__name__.replace("Controller", "").lower()
                view_template = render_template(f'{cname}/{name}.html', **self.__dict__)
                return view_template
            return wrapper
        return getattr(super(), name)


params = ParamsProxy()


def redirect_to(url):
    raise Redirect(redirect(url))
