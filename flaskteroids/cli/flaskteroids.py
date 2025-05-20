import os
import click
from flaskteroids.cli.artifacts import ArtifactsBuilder, ArtifactsBuilderException


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
        ab.file('README.md')
        ab.file('Dockerfile')
        ab.file('.gitignore', _gitignore())
        ab.file('.flaskenv', _flaskenv())
        ab.file('run.py', _run())
        ab.dir('db/')
        ab.dir('app/')
        ab.file('app/assets/stylesheets/application.css')
        ab.file('app/assets/images/.keep')
        ab.file('app/helpers/application_helper.py')
        ab.file('app/models/application_model.py', _application_model())
        ab.file('app/jobs/application_job.py')
        ab.file('app/mailers/application_mailer.py', _application_mailer())
        ab.file('app/views/layouts/application.html')
        ab.file('app/views/layouts/mailer.html')
        ab.file('app/views/layouts/mailer.txt')
        ab.file('app/controllers/application_controller.py', _application_controller())
        ab.file('config/routes.py', _routes())
        ab.run('flask db:init')
        ab.run('git init')
        ab.run('git branch -m main')
    except ArtifactsBuilderException as e:
        click.echo(f"Error creating new flaskteroids app: {e}")


def _gitignore():
    return """
__pycache__/
.venv/
db/database.db
db/jobs_database.db
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


def _run():
    return """
import logging
from flaskteroids.app import create_app

app = create_app(__name__)
jobs_app = app.extensions['flaskteroids.jobs']


if __name__ == '__main__':
    app.run(debug=True)
    """


def _flaskenv():
    return """
FLASK_APP=run.py
    """
