import click
from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.cli.generators.model import generator as model
from flaskteroids.cli.generators.src_modifier import add_routes
from flaskteroids.cli.generators.templates import template
from flaskteroids.cli.generators.scaffold import cmd_parser


def generate(name: str, args: list[str]):
    params = cmd_parser.parse(name, args)['parsed']
    ab = ArtifactsBuilder('.', click.echo)
    plural = params['plural']
    singular = params['singular']
    ab.file(
        f'app/controllers/{plural}_controller.py',
        _template(path='app/controllers/controller.py.mako', params=params)
    )
    ab.file(f'app/views/{plural}/index.html', _template(path='app/views/index.html.mako', params=params))
    ab.file(f'app/views/{plural}/index.html', _template(path='app/views/index.html.mako', params=params))
    ab.file(f'app/views/{plural}/new.html', _template(path='app/views/new.html.mako', params=params))
    ab.file(f'app/views/{plural}/edit.html', _template(path='app/views/edit.html.mako', params=params))
    ab.file(f'app/views/{plural}/show.html', _template(path='app/views/show.html.mako', params=params))
    ab.file(f'app/views/{plural}/_form.html', _template(path='app/views/_form.html.mako', params=params))
    ab.file(f'app/views/{plural}/_{singular}.html', _template(path='app/views/_record.html.mako', params=params))
    ab.modify_py_file('config/routes.py', add_routes([
        f"route.resources('{plural}')",
    ]))
    model.generate(params['model'], args)


def _template(*, path, params=None):
    return template('flaskteroids.cli.generators.scaffold.templates', path=path, params=params)
