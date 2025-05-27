import click
from importlib.resources import files, as_file
from mako.lookup import TemplateLookup
from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.cli.generators.migrations import generator as migrations
from flaskteroids.cli.generators.src_modifier import add_routes


def generate():
    ab = ArtifactsBuilder('.', click.echo)
    ab.file(
        'app/models/session.py',
        _template(path='app/models/session.py.mako')
    )
    ab.file(
        'app/models/user.py',
        _template(path='app/models/user.py.mako')
    )
    ab.file(
        'app/controllers/concerns/authentication.py',
        _template(path='app/controllers/concerns/authentication.py.mako')
    )
    ab.file(
        'app/controllers/sessions_controller.py',
        _template(path='app/controllers/sessions_controller.py.mako')
    )
    ab.file(
        'app/controllers/passwords_controller.py',
        _template(path='app/controllers/passwords_controller.py.mako')
    )
    ab.file(
        'app/mailers/passwords_mailer.py',
        _template(path='app/mailers/passwords_mailer.py.mako')
    )
    ab.modify_py_file('config/routes.py', add_routes([
        "route.resource('session')",
        "route.resources('passwords')",
    ]))
    migrations.generate('CreateUsersTable', ['email_address:str!', 'password_digest:str!'])
    migrations.generate('CreateSessionsTable', ['user:references', 'ip_address:str', 'user_agent:str'])


def _template(*, path, params=None):
    with as_file(files('flaskteroids.cli.generators.authentication.templates')) as templates_dir:
        template_lookup = TemplateLookup(directories=[str(templates_dir)])
        params = params or {}
        template = template_lookup.get_template(path)
        return template.render(**params)
