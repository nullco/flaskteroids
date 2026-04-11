import click
from cucurbit.cli.artifacts import ArtifactsBuilder
from cucurbit.cli.generators.model import generator as model
from cucurbit.cli.generators.src_modifier import add_routes
from cucurbit.cli.generators.templates import template
from cucurbit.cli.generators.resource import cmd_parser


def generate(name: str, args: list[str]):
    params = cmd_parser.parse(name, args)['parsed']
    ab = ArtifactsBuilder('.', click.echo)
    plural = params['plural']
    ab.file(
        f'app/controllers/{plural}_controller.py',
        _template(path='app/controllers/controller.py.mako', params=params)
    )
    ab.modify_py_file('config/routes.py', add_routes([
        f"route.resources('{plural}')",
    ]))
    model.generate(params['model'], args)


def _template(*, path, params=None):
    return template('cucurbit.cli.generators.resource', path=path, params=params)
