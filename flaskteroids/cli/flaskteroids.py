import os
import textwrap
import click
from pathlib import Path


@click.group()
def cli():
    pass


@cli.command('new')
@click.argument('app_name')
def new(app_name):
    NewAppBuilder(os.path.abspath(app_name)).build()


class NewAppBuilder:

    def __init__(self, base_path: str):
        self._base_path = base_path

    def build(self):
        try:
            os.makedirs(self._base_path, exist_ok=True)
            self._file('README.md')
            self._file('Dockerfile')
            self._file('.gitignore', _gitignore())
            self._file('.flaskenv', _flaskenv())
            self._file('run.py', _run())
            self._dir('db/')
            self._dir('app/')
            self._file('app/assets/stylesheets/application.css')
            self._file('app/assets/images/.keep')
            self._file('app/helpers/application_helper.py')
            self._file('app/models/application_model.py')
            self._file('app/jobs/application_job.py')
            self._file('app/mailers/application_mailer.py', _application_mailer())
            self._file('app/views/layouts/application.html')
            self._file('app/views/layouts/mailer.html')
            self._file('app/views/layouts/mailer.txt')
            self._file('app/controllers/application_controller.py', _application_controller())
            self._file('config/routes.py', _routes())
        except Exception as e:
            click.echo(f"Error creating new flaskteroids app: {e}")

    def _join(self, name):
        return Path(self._base_path, name)

    def _dir(self, name):
        os.makedirs(self._join(name), exist_ok=True)
        click.echo(f"    create  {name}")

    def _file(self, name, contents=None):
        file_path = self._join(name)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch(exist_ok=True)
        if contents:
            file_path.write_text(self._clean(contents))
        click.echo(f"    create  {name}")

    def _clean(self, txt: str):
        return textwrap.dedent(txt).lstrip()


def _gitignore():
    return """
__pycache__/
db/database.db
db/jobs_database.db
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
