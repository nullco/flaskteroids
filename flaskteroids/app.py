import logging
from http import HTTPStatus
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import default_exceptions
from flaskteroids.extensions.mail import MailExtension
import flaskteroids.model as model
from flaskteroids.db import session
from flaskteroids.flash import flash
from flaskteroids import helpers
from flaskteroids.csrf import CSRFToken
from flaskteroids.extensions.jobs import JobsExtension
from flaskteroids.extensions.db import SQLAlchemyExtension
from flaskteroids.extensions.routes import RoutesExtension
from flaskteroids.cli.generators import commands as generate_commands
from flaskteroids.cli.db import commands as db_commands
from flaskteroids.cli import credentials as credentials_commands


_logger = logging.getLogger(__name__)


def initialize_app(app):
    app.wsgi_app = ProxyFix(app.wsgi_app)
    _configure_orm(app)
    _prepare_shell_context(app)
    _prepare_template_contexts(app)
    _register_error_handlers(app)
    _register_cli_commands(app)
    _setup_csrf(app)
    _setup_jobs(app)
    _setup_mailers(app)


def finalize_app(app):
    _register_routes(app)


def _register_routes(app):
    RoutesExtension(app)


def _configure_orm(app):
    SQLAlchemyExtension(app)


def _register_error_handlers(app):

    def handle_error(code):
        def _(e):
            HttpExceptionClass = default_exceptions.get(code)
            if HttpExceptionClass:
                return HttpExceptionClass(description=str(e)).get_response()
            raise e
        return _

    app.register_error_handler(model.RecordNotFoundException, handle_error(HTTPStatus.NOT_FOUND))


def _register_cli_commands(app):
    app.cli.add_command(generate_commands.generate, name='generate')
    app.cli.add_command(generate_commands.generate, name='g')
    app.cli.add_command(db_commands.init)
    app.cli.add_command(db_commands.migrate)
    app.cli.add_command(db_commands.rollback)
    app.cli.add_command(credentials_commands.show)
    app.cli.add_command(credentials_commands.edit)


def _prepare_shell_context(app):

    @app.shell_context_processor
    def _():
        _logger.debug('Preparing shell context')
        db = app.extensions['flaskteroids.db']

        def commit(fn):
            """This commits immediately changes on models from the shell"""
            def wrapper(*args, **kwargs):
                res = fn(*args, **kwargs)
                session.commit()
                return res
            return wrapper

        for model_cls in db.models.values():
            model_cls.create = commit(model_cls.create)
            model_cls.update = commit(model_cls.update)
            model_cls.save = commit(model_cls.save)
            model_cls.destroy = commit(model_cls.destroy)

        return {
            **db.models,
        }


def _prepare_template_contexts(app):

    db = app.extensions['flaskteroids.db']

    app.jinja_env.globals['render'] = helpers.render
    app.jinja_env.globals['button_to'] = helpers.button_to
    app.jinja_env.globals['link_to'] = helpers.link_to
    app.jinja_env.globals['form_with'] = helpers.form_with
    app.jinja_env.globals['csrf_token'] = CSRFToken(app.config.get('SECRET_KEY')).generate

    @app.context_processor
    def _():
        return {
            'flash': flash.messages,
            **db.models
        }


def _setup_csrf(app):
    @app.before_request
    def _():
        csrft = CSRFToken(app.config.get('SECRET_KEY'))
        csrft.validate()


def _setup_jobs(app):
    JobsExtension(app)


def _setup_mailers(app):
    MailExtension(app)
