import click
from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.cli.generators.src_modifier import add_routes
from flaskteroids.inflector import inflector


def generate(controller, actions, skip_routes=False):
    ab = ArtifactsBuilder('.', click.echo)
    cname = inflector.underscore(controller)
    ab.file(
        f'app/controllers/{cname}_controller.py',
        _controller(name=controller, actions=actions)
    )
    ab.file(
        f'app/helpers/{cname}_helper.py',
        _helper(name=controller)
    )
    ab.dir(f'app/views/{cname}/')
    for action in actions:
        file_name = f'app/views/{cname}/{action}.html'
        ab.file(file_name, _view(name=controller, action=action, file_name=file_name))
        if not skip_routes:
            route = f"route.get('/{cname}/{action}', to='{cname}#{action}')"
            ab.modify_py_file('config/routes.py', add_routes([route]))


def _helper(*, name):
    return f"""
class {name}Helper:
    pass
    """


def _controller(*, name, actions):
    action_fns = []
    for action in actions:
        action_fns.append(f"""
    def {action}(self):
        pass
        """)
    action_fns = ''.join(action_fns) or 'pass'
    return f"""
from app.controllers.application_controller import ApplicationController


class {name}Controller(ApplicationController):
    {action_fns}"""


def _view(name, action, file_name):
    return f"""
<h1>{name}#{action}</h1>
<p>Find me in {file_name}</p>
    """
