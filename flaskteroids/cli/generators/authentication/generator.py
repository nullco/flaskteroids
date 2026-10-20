import click

from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.cli.generators.migrations import generator as migrations
from flaskteroids.cli.generators.src_modifier import (
    add_base_cls,
    add_imports,
    add_routes,
)
from flaskteroids.cli.generators.templates import template


def generate():
    ab = ArtifactsBuilder(".", click.echo)
    ab.file("app/models/session.py", _template(path="app/models/session.py.mako"))
    ab.file("app/models/user.py", _template(path="app/models/user.py.mako"))
    ab.file(
        "app/views/sessions/new.html", _template(path="app/views/sessions/new.html")
    )
    ab.file(
        "app/views/passwords/new.html", _template(path="app/views/passwords/new.html")
    )
    ab.file(
        "app/views/passwords/edit.html", _template(path="app/views/passwords/edit.html")
    )
    ab.file(
        "app/views/passwords_mailer/reset.html",
        _template(path="app/views/passwords_mailer/reset.html"),
    )
    ab.file(
        "app/views/passwords_mailer/reset.txt",
        _template(path="app/views/passwords_mailer/reset.txt"),
    )
    ab.file(
        "app/controllers/concerns/authentication.py",
        _template(path="app/controllers/concerns/authentication.py.mako"),
    )
    ab.file(
        "app/controllers/sessions_controller.py",
        _template(path="app/controllers/sessions_controller.py.mako"),
    )
    ab.file(
        "app/controllers/passwords_controller.py",
        _template(path="app/controllers/passwords_controller.py.mako"),
    )
    ab.file(
        "app/mailers/passwords_mailer.py",
        _template(path="app/mailers/passwords_mailer.py.mako"),
    )
    ab.file("test/models/user_test.py", _model_test("User"))
    ab.file("test/models/session_test.py", _model_test("Session"))
    ab.file("test/controllers/sessions_controller_test.py", _sessions_test())
    ab.file("test/controllers/passwords_controller_test.py", _passwords_test())
    ab.modify_py_file(
        "app/controllers/application_controller.py",
        add_imports(
            ["from app.controllers.concerns.authentication import Authentication"]
        ),
    )
    ab.modify_py_file(
        "app/controllers/application_controller.py", add_base_cls("Authentication")
    )
    ab.modify_py_file(
        "config/routes.py",
        add_routes(
            [
                "route.resource('session', only=['new', 'create', 'destroy'])",
                "route.resources('passwords', param='token', only=['new', 'create', 'edit', 'update'])",
            ]
        ),
    )
    migrations.generate("CreateUsers", ["email_address:str!", "password_digest:str!"])
    migrations.generate(
        "CreateSessions", ["user:references", "ip_address:str", "user_agent:str"]
    )


def _model_test(name):
    return _template(path="test/models/model_test.py.mako", params={"name": name})


def _sessions_test():
    return _template(path="test/controllers/sessions_test.py.mako", params=None)


def _passwords_test():
    return _template(path="test/controllers/passwords_test.py.mako", params=None)


def _template(*, path, params=None):
    return template(
        "flaskteroids.cli.generators.authentication", path=path, params=params
    )
