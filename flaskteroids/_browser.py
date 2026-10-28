"""Browser facilities installed together at the application composition root."""

from flask import has_request_context

from flaskteroids import helpers
from flaskteroids._method_override import MethodOverrideMiddleware
from flaskteroids.assets import init_assets
from flaskteroids.csrf import CSRFToken
from flaskteroids.flash import flash
from flaskteroids.importmaps.extension import init_importmaps
from flaskteroids.rich_text.extension import init_rich_text
from flaskteroids.rich_text.helpers import rich_text_assets
from flaskteroids.turbo import dom_class, dom_id, turbo_frame_tag, turbo_stream
from flaskteroids.turbo.extension import init_turbo
from flaskteroids.turbo.extension import template_context as turbo_template_context


def install_browser(app):
    app.wsgi_app = MethodOverrideMiddleware(app, app.wsgi_app)
    app.jinja_env.globals.update(
        dom_id=dom_id,
        dom_class=dom_class,
        turbo_frame_tag=turbo_frame_tag,
        turbo_stream=turbo_stream,
        button_to=helpers.button_to,
        form_with=helpers.form_with,
        csrf_token=CSRFToken(app.secret_key).generate,
        rich_text_assets=rich_text_assets,
        javascript_importmap_tags=helpers.javascript_importmap_tags,
        importmap_digest=helpers.importmap_digest,
        javascript_import_module_tag=helpers.javascript_import_module_tag,
        javascript_inline_importmap_tag=helpers.javascript_inline_importmap_tag,
        javascript_module_preload_tag=helpers.javascript_module_preload_tag,
    )

    init_turbo(app)
    init_rich_text(app)
    init_assets(app)
    init_importmaps(app)


def browser_context():
    return {
        "flash": flash.messages if has_request_context() else {},
        **turbo_template_context(),
    }
