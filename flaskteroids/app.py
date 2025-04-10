from flask.app import Flask
from importlib import import_module
from flaskteroids.exceptions import Redirect
import flaskteroids.route as route
import flaskteroids.model as model
from flaskteroids.extensions.forms import FormsExtension
from flaskteroids.extensions.celery import CeleryExtension
from flaskteroids.extensions.db import ORMExtension
from flaskteroids.cli.generators import generator as generate_cmd
from flaskteroids.cli.db import db as db_cmd


def create_app(import_name, config_dict=None):
    app = Flask(import_name, template_folder='app/views/')
    if config_dict:
        app.config.update(config_dict)

    _register_routes(app)
    _configure_orm(app)
    _prepare_shell_context(app)
    _register_error_handlers(app)
    _register_cli_commands(app)
    _setup_forms(app)
    _setup_jobs(app)

    return app


def _register_routes(app):
    rr = route.init(app)
    routes = import_module('app.config.routes')
    routes.register(rr)
    if not rr.has_path('/'):
        rr.root(to='flaskteroids/welcome#show')


def _configure_orm(app):
    ORMExtension(app)


def _register_error_handlers(app):

    def handle_4xx(error):
        return '400 Error, sorry masamorry'

    def handle_redirect(redirect):
        return redirect.response

    app.register_error_handler(model.ModelNotFoundException, handle_4xx)
    app.register_error_handler(Redirect, handle_redirect)


def _register_cli_commands(app):
    app.cli.add_command(generate_cmd.generate)
    app.cli.add_command(db_cmd.init)
    app.cli.add_command(db_cmd.migrate)


def _prepare_shell_context(app):
    @app.shell_context_processor
    def _():
        db = app.extensions['flaskteroids.db']
        return {
            **db.models,
            'reload': db.init_models
        }


def _setup_forms(app):
    FormsExtension(app)


def _setup_jobs(app):
    CeleryExtension(app)
