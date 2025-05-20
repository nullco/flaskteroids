import ast
import click
from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.str_utils import camel_to_snake


def generate(controller, actions, skip_routes=False):
    ab = ArtifactsBuilder('.', click.echo)
    ab.file(
        f'app/controllers/{camel_to_snake(controller)}_controller.py',
        _controller(name=controller, actions=actions)
    )
    ab.file(
        f'app/helpers/{camel_to_snake(controller)}_helper.py',
        _helper(name=controller)
    )
    ab.dir(f'app/views/{camel_to_snake(controller)}/')
    for action in actions:
        file_name = f'app/views/{camel_to_snake(controller)}/{action}.html'
        ab.file(file_name, _view(name=controller, action=action, file_name=file_name))
        if not skip_routes:
            ab.modify_py_file('config/routes.py', _add_route(camel_to_snake(controller), action))


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
    action_fns = ''.join(action_fns)
    return f"""
from app.controllers.application_controller import ApplicationController


class {name}Controller(ApplicationController):
    {action_fns}"""


def _view(name, action, file_name):
    return f"""
<h1>{name}#{action}</h1>
<p>Find me in {file_name}</p>
    """


def _add_route(name, action):
    class AddRoute(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            if node.name == "register":
                new_stmt = ast.parse(f"route.get('/{name}/{action}/', to='{name}#{action}')").body[0]
                node.body.insert(1, new_stmt)
            return node
    return AddRoute
