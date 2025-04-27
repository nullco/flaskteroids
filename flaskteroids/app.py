from flask.app import Flask
from flaskteroids.exceptions import Redirect
from flaskteroids.extensions.mail import MailExtension
import flaskteroids.model as model
from flaskteroids.extensions.forms import FormsExtension
from flaskteroids.extensions.jobs import JobsExtension
from flaskteroids.extensions.db import SQLAlchemyExtension
from flaskteroids.extensions.routes import RoutesExtension
from flaskteroids.cli.generators import commands as generate_commands
from flaskteroids.cli.db import commands as db_commands


def create_app(import_name, config=None):
    config = _config(config)
    app = Flask(import_name, template_folder=config['VIEWS_FOLDER'])

    _attach_config(app, config)
    _register_routes(app)
    _configure_orm(app)
    _prepare_shell_context(app)
    _register_error_handlers(app)
    _register_cli_commands(app)
    _setup_forms(app)
    _setup_jobs(app)
    _setup_mailers(app)

    return app


def _config(overwrites):
    cfg = {
        'ROUTES_PACKAGE': 'app.config.routes',
        'MODELS_PACKAGE': 'app.models',
        'JOBS_PACKAGE': 'app.jobs',
        'VIEWS_FOLDER': 'app/views/',
        'SQLALCHEMY_URL': 'sqlite:///db/database.db',
        'JOBS': {
            'CELERY_BROKER_URL': 'sqla+sqlite:///db/jobs_database.db'
        },
        'MAIL_ENABLED': False
    }
    if overwrites:
        cfg.update(overwrites)
    return cfg


def _attach_config(app, config):
    if config:
        app.config.update(config)


def _register_routes(app):
    RoutesExtension(app)


def _configure_orm(app):
    SQLAlchemyExtension(app)


def _register_error_handlers(app):

    def handle_4xx(error):
        return '400 Error, sorry masamorry'

    def handle_redirect(redirect):
        return redirect.response

    app.register_error_handler(model.ModelNotFoundException, handle_4xx)
    app.register_error_handler(Redirect, handle_redirect)


def _register_cli_commands(app):
    app.cli.add_command(generate_commands.generate)
    app.cli.add_command(db_commands.init)
    app.cli.add_command(db_commands.migrate)


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
    JobsExtension(app)


def _setup_mailers(app):
    MailExtension(app)
