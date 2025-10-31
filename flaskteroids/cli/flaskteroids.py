import os
import click
from flaskteroids.cli.artifacts import ArtifactsBuilder, ArtifactsBuilderException
from flaskteroids.cli.generators.templates import template


@click.group()
def cli():
    pass


@cli.command('new')
@click.argument('app_name')
def new(app_name):
    base_path = os.path.abspath(app_name)
    ab = ArtifactsBuilder(base_path, click.echo)
    try:
        ab.dir()
        ab.file('README.md', _readme(app_name))
        ab.file('Dockerfile')
        ab.file('.gitignore', _gitignore())
        ab.file('pyproject.toml', _pyproject_toml(app_name))
        ab.file('wsgi.py', _wsgi())
        ab.file('jobs.py', _jobs())
        ab.file('storage/.keep')
        ab.dir('db/')
        ab.dir('app/')
        ab.file('app/assets/stylesheets/application.css')
        ab.file('app/assets/images/.keep')
        ab.file('app/helpers/application_helper.py', _application_helper())
        ab.file('app/models/application_model.py', _application_model())
        ab.file('app/jobs/application_job.py')
        ab.file('app/mailers/application_mailer.py', _application_mailer())
        ab.file('app/views/layouts/application.html', _template(path='app/views/layouts/application.html.mako'))
        ab.file('app/views/layouts/mailer.html')
        ab.file('app/views/layouts/mailer.txt')
        ab.file('app/controllers/application_controller.py', _application_controller())
        ab.file('config/routes.py', _routes())
        ab.run('flask db:init')
        ab.file('db/migrate/versions/.keep')
        ab.run('git init')
        ab.run('git branch -m main')
    except ArtifactsBuilderException as e:
        click.echo(f"Error creating new flaskteroids app: {e}")


def _gitignore():
    return """
__pycache__/
.venv/
storage/database.db
storage/jobs_database.db
    """


def _readme(app_name):
    return f"""
# {app_name.replace('_', ' ').title()}

Add your project description here
    """


def _pyproject_toml(app_name):
    return f"""
[project]
name = "{app_name}"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "flaskteroids",
]
    """


def _application_helper():
    return """
class ApplicationHelper:
    pass
    """


def _application_model():
    return """
from flaskteroids.model import Model


class ApplicationModel(Model):
    pass
    """


def _application_controller():
    return """
from flaskteroids.controller import ActionController


class ApplicationController(ActionController):
    pass
    """


def _application_mailer():
    return """
from flaskteroids.mailer import ActionMailer


class ApplicationMailer(ActionMailer):
    pass
    """


def _routes():
    return """
def register(route):
    route.get('/up/', to="flaskteroids/health#show")
    """


def _wsgi():
    return """
from flaskteroids.app import create_app

app = create_app(__name__)

if __name__ == '__main__':
    app.run(debug=True)
    """


def _jobs():
    return """
from flaskteroids.app import create_app

app = create_app(__name__).extensions['flaskteroids.jobs']
    """


def _template(*, path, params=None):
    return template('flaskteroids.cli.templates', path=path, params=params)
