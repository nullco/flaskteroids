import logging
from http import HTTPStatus

from flask import has_request_context, request
from werkzeug.exceptions import default_exceptions
from werkzeug.middleware.proxy_fix import ProxyFix

from flaskteroids import helpers, model
from flaskteroids.assets import init_assets
from flaskteroids.attachments import UploadTooLarge, blob_path, blob_url
from flaskteroids.attachments.extension import AttachmentsExtension
from flaskteroids.cache.inmemory import InMemoryCache
from flaskteroids.cli import credentials as credentials_commands
from flaskteroids.cli import testing as testing_commands
from flaskteroids.cli.assets import precompile as assets_precompile
from flaskteroids.cli.attachments import install as attachments_install
from flaskteroids.cli.db import commands as db_commands
from flaskteroids.cli.db.snapshot import dump as schema_dump
from flaskteroids.cli.generators import commands as generate_commands
from flaskteroids.cli.rich_text import install as rich_text_install
from flaskteroids.cli.turbo import install as turbo_install
from flaskteroids.csrf import CSRFToken
from flaskteroids.db import session
from flaskteroids.exceptions import InvalidParameter, MissingParameter
from flaskteroids.extensions.db import SQLAlchemyExtension
from flaskteroids.extensions.helpers import HelpersExtension
from flaskteroids.extensions.jobs import JobsExtension
from flaskteroids.extensions.mail import MailExtension
from flaskteroids.extensions.routes import RoutesExtension
from flaskteroids.flash import flash
from flaskteroids.i18n import I18nExtension
from flaskteroids.rich_text.extension import init_rich_text
from flaskteroids.rich_text.helpers import rich_text_assets
from flaskteroids.turbo import dom_class, dom_id, turbo_frame_tag, turbo_stream
from flaskteroids.turbo.extension import init_turbo
from flaskteroids.turbo.extension import template_context as turbo_template_context

_logger = logging.getLogger(__name__)


def initialize_app(app):
    if vars(app).get("_flaskteroids_initialized", False):
        return
    app.extensions.setdefault("flaskteroids.cache", InMemoryCache())
    app.wsgi_app = ProxyFix(app.wsgi_app)
    _configure_orm(app)
    _prepare_shell_context(app)
    _prepare_template_contexts(app)
    I18nExtension(app)
    HelpersExtension(app)
    init_turbo(app)
    _register_error_handlers(app)
    _register_cli_commands(app)
    _setup_csrf(app)
    _setup_jobs(app)
    _setup_mailers(app)
    AttachmentsExtension(app)
    init_rich_text(app)
    init_assets(app)
    app._flaskteroids_initialized = True


def finalize_app(app):
    if vars(app).get("_flaskteroids_finalized", False):
        return
    _register_routes(app)
    app._flaskteroids_finalized = True


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

    for exception in (MissingParameter, InvalidParameter):
        app.register_error_handler(exception, handle_error(HTTPStatus.BAD_REQUEST))
    app.register_error_handler(
        model.RecordNotFoundException, handle_error(HTTPStatus.NOT_FOUND)
    )
    app.register_error_handler(
        UploadTooLarge, handle_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
    )


def _register_cli_commands(app):
    app.cli.add_command(generate_commands.generate, name="generate")
    app.cli.add_command(generate_commands.generate, name="g")
    app.cli.add_command(db_commands.init)
    app.cli.add_command(db_commands.create)
    app.cli.add_command(db_commands.migrate)
    app.cli.add_command(db_commands.prepare)
    app.cli.add_command(db_commands.rollback)
    app.cli.add_command(schema_dump)
    app.cli.add_command(credentials_commands.show)
    app.cli.add_command(credentials_commands.edit)
    app.cli.add_command(testing_commands.test)
    app.cli.add_command(testing_commands.test_system)
    app.cli.add_command(attachments_install)
    app.cli.add_command(rich_text_install)
    app.cli.add_command(turbo_install)
    app.cli.add_command(db_commands.encryption_init)
    app.cli.add_command(assets_precompile)


def _prepare_shell_context(app):

    @app.shell_context_processor
    def _():
        _logger.debug("Preparing shell context")
        db = app.extensions["flaskteroids.db"]

        return {**db.models, "session": session}


def _prepare_template_contexts(app):

    db = app.extensions["flaskteroids.db"]

    app.jinja_env.globals["dom_id"] = dom_id
    app.jinja_env.globals["dom_class"] = dom_class
    app.jinja_env.globals["turbo_frame_tag"] = turbo_frame_tag
    app.jinja_env.globals["turbo_stream"] = turbo_stream
    app.jinja_env.globals["render"] = helpers.render
    app.jinja_env.globals["button_to"] = helpers.button_to
    app.jinja_env.globals["link_to"] = helpers.link_to
    app.jinja_env.globals["form_with"] = helpers.form_with
    app.jinja_env.globals["csrf_token"] = CSRFToken(
        app.config.get("SECRET_KEY")
    ).generate
    app.jinja_env.globals["blob_path"] = blob_path
    app.jinja_env.globals["blob_url"] = blob_url
    app.jinja_env.globals["rich_text_assets"] = rich_text_assets

    @app.context_processor
    def _():
        return {
            "flash": flash.messages if has_request_context() else {},
            **db.models,
            **app.extensions["flaskteroids.helpers"].template_context(),
            **turbo_template_context(),
        }


def _setup_csrf(app):
    @app.before_request
    def _():
        if request.environ.get("flaskteroids.routing_error"):
            raise request.routing_exception
        csrft = CSRFToken(app.config.get("SECRET_KEY"))
        csrft.validate()


def _setup_jobs(app):
    JobsExtension(app)


def _setup_mailers(app):
    MailExtension(app)
