import click

from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.cli.generators.model import generator as model
from flaskteroids.cli.generators.resource import cmd_parser
from flaskteroids.cli.generators.src_modifier import add_routes
from flaskteroids.cli.generators.templates import template


def generate(name: str, args: list[str]):
    params = cmd_parser.parse(name, args)["parsed"]
    ab = ArtifactsBuilder(".", click.echo)
    plural = params["plural"]
    ab.file(
        f"app/controllers/{plural}_controller.py",
        _template(path="app/controllers/controller.py.mako", params=params),
    )
    ab.file(
        f"test/controllers/{plural}_controller_test.py",
        _controller_test(params["controller"]),
    )
    ab.modify_py_file(
        "config/routes.py",
        add_routes(
            [
                f"route.resources('{plural}')",
            ]
        ),
    )
    model.generate(params["model"], args)


def _controller_test(controller):
    return _template(
        path="test/controllers/controller_test.py.mako",
        params={"controller": controller},
    )


def _template(*, path, params=None):
    return template("flaskteroids.cli.generators.resource", path=path, params=params)
