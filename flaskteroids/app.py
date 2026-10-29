import logging

from flask import request
from werkzeug.middleware.proxy_fix import ProxyFix

from flaskteroids import helpers
from flaskteroids._application_stack import application_stack
from flaskteroids._http_errors import register_error_handlers
from flaskteroids._request_policy import request_policy
from flaskteroids.attachments import blob_path, blob_url
from flaskteroids.attachments.extension import AttachmentsExtension
from flaskteroids.cache.inmemory import InMemoryCache
from flaskteroids.cli import credentials as credentials_commands
from flaskteroids.cli.attachments import install as attachments_install
from flaskteroids.cli.db import commands as db_commands
from flaskteroids.cli.db.snapshot import dump as schema_dump
from flaskteroids.cli.generators import commands as generate_commands
from flaskteroids.cli.importmap import install as importmap_install
from flaskteroids.cli.rich_text import install as rich_text_install
from flaskteroids.cli.turbo import install as turbo_install
from flaskteroids.db import session
from flaskteroids.extensions.db import SQLAlchemyExtension
from flaskteroids.extensions.helpers import HelpersExtension
from flaskteroids.extensions.jobs import JobsExtension
from flaskteroids.extensions.mail import MailExtension
from flaskteroids.extensions.mail_previews import MailPreviewsExtension
from flaskteroids.extensions.routes import RoutesExtension
from flaskteroids.i18n import I18nExtension

_logger = logging.getLogger(__name__)


def initialize_app(app):
    if vars(app).get("_flaskteroids_initialized", False):
        return
    stack = application_stack(app.config)
    app.extensions["flaskteroids.stack"] = stack
    app.extensions.setdefault("flaskteroids.cache", InMemoryCache())
    _configure_orm(app)
    _prepare_shell_context(app)
    _prepare_template_contexts(app, stack.template_context)
    I18nExtension(app)
    HelpersExtension(app)
    register_error_handlers(app, stack.requests)
    _register_cli_commands(app)
    _setup_request_protection(app, stack.requests)
    _setup_jobs(app)
    _setup_mailers(app)
    AttachmentsExtension(app)
    stack.install(app)
    app.wsgi_app = ProxyFix(app.wsgi_app)
    app._flaskteroids_initialized = True


def finalize_app(app):
    if vars(app).get("_flaskteroids_finalized", False):
        return
    _register_routes(app)
    MailPreviewsExtension(app)
    app._flaskteroids_finalized = True


def _register_routes(app):
    RoutesExtension(app)


def _configure_orm(app):
    SQLAlchemyExtension(app)


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
    app.cli.add_command(attachments_install)
    app.cli.add_command(rich_text_install)
    app.cli.add_command(turbo_install)
    app.cli.add_command(importmap_install)
    app.cli.add_command(db_commands.encryption_init)


def _prepare_shell_context(app):

    @app.shell_context_processor
    def _():
        _logger.debug("Preparing shell context")
        db = app.extensions["flaskteroids.db"]

        return {**db.models, "session": session}


def _prepare_template_contexts(app, template_context):

    db = app.extensions["flaskteroids.db"]

    app.jinja_env.globals.update(
        render=helpers.render,
        link_to=helpers.link_to,
        blob_path=blob_path,
        blob_url=blob_url,
    )

    @app.context_processor
    def _():
        return {
            **db.models,
            **app.extensions["flaskteroids.helpers"].template_context(),
            **template_context(),
        }


def _setup_request_protection(app, default_policy):
    @app.before_request
    def _():
        if request.environ.get("flaskteroids.routing_error"):
            raise request.routing_exception
        request_policy(default_policy).protect()


def _setup_jobs(app):
    JobsExtension(app)


def _setup_mailers(app):
    MailExtension(app)
