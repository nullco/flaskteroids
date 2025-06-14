import click
from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.cli.generators.migrations import generator as migrations
from flaskteroids.cli.generators.src_modifier import add_routes, add_imports, add_base_cls
from flaskteroids.cli.generators.templates import template


def generate():
    ab = ArtifactsBuilder('.', click.echo)
    ab.file('app/models/session.py', _template(path='app/models/session.py.mako'))
    ab.file('app/models/user.py', _template(path='app/models/user.py.mako'))
    ab.file('app/views/sessions/new.html', _template(path='app/views/sessions/new.html'))
    ab.file('app/views/passwords/new.html', _template(path='app/views/passwords/new.html'))
    ab.file('app/views/passwords/edit.html', _template(path='app/views/passwords/edit.html'))
    ab.file('app/views/passwords_mailer/reset.html', _template(path='app/views/passwords_mailer/reset.html'))
    ab.file('app/views/passwords_mailer/reset.txt', _template(path='app/views/passwords_mailer/reset.txt'))
    ab.file('app/controllers/concerns/authentication.py',
            _template(path='app/controllers/concerns/authentication.py.mako'))
    ab.file('app/controllers/sessions_controller.py', _template(path='app/controllers/sessions_controller.py.mako'))
    ab.file('app/controllers/passwords_controller.py', _template(path='app/controllers/passwords_controller.py.mako'))
    ab.file('app/mailers/passwords_mailer.py', _template(path='app/mailers/passwords_mailer.py.mako'))
    ab.modify_py_file(
        'app/controllers/application_controller.py',
        add_imports([
            "from app.controllers.concerns.authentication import Authentication"
        ])
    )
    ab.modify_py_file('app/controllers/application_controller.py', add_base_cls("Authentication"))
    ab.modify_py_file('config/routes.py', add_routes([
        "route.resource('session')",
        "route.resources('passwords', param='token')",
    ]))
    migrations.generate('CreateUsersTable', ['email_address:str!', 'password_digest:str!'])
    migrations.generate('CreateSessionsTable', ['user:references', 'ip_address:str', 'user_agent:str'])


def _template(*, path):
    return template('flaskteroids.cli.generators.authentication.templates', path=path)
