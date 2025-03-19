from flask.app import Flask
from importlib import import_module
import flaskteroids.route as route
import flaskteroids.db as db
import flaskteroids.model as model
from flaskteroids.cli.generators import generator as generate_cmd
from flaskteroids.cli.db import db as db_cmd


def create_app(import_name, config_dict=None):
    app = Flask(import_name, template_folder='app/views/')
    if config_dict:
        app.config.update(config_dict)

    _register_routes(app)
    _configure_database(app)
    _register_error_handlers(app)
    _register_cli_commands(app)

    return app


def _register_routes(app):
    rr = route.init(app)
    routes = import_module('app.config.routes')
    routes.register(rr)


def _configure_database(app):
    db.configure(app)


def _register_error_handlers(app):

    def handle_4xx(error):
        return '400 Error, sorry masamorry'

    app.register_error_handler(model.ModelNotFoundException, handle_4xx)


def _register_cli_commands(app):
    app.cli.add_command(generate_cmd.generate)
    app.cli.add_command(db_cmd.init)
    app.cli.add_command(db_cmd.migrate)
