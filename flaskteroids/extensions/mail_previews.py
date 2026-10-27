import inspect
import sys
from importlib.util import module_from_spec, spec_from_file_location
from urllib.parse import urlencode

from flask import Blueprint, abort, request, url_for
from jinja2 import Environment, PackageLoader

from flaskteroids._branding import brand_images
from flaskteroids._mailer_preview import MailerPreview
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.inflector import inflector
from flaskteroids.mailer import MessageDelivery

_templates = Environment(
    loader=PackageLoader("flaskteroids", "templates/mailers"),
    autoescape=True,
)


class MailPreviewsExtension:
    def __init__(self, app):
        enabled = app.config.mailer.show_previews
        if enabled is None:
            enabled = app.env.development
        if not enabled:
            return

        previews = _discover_previews(app)
        blueprint = Blueprint(
            "flaskteroids_mail_previews",
            __name__,
            url_prefix="/flaskteroids/mailers",
        )

        @blueprint.get("", strict_slashes=False)
        def index():
            return _render("index.html", previews=previews)

        @blueprint.get("/<path:target>")
        def show(target):
            if target in previews:
                return _render("index.html", previews={target: previews[target]})
            preview, _, email = target.rpartition("/")
            entry = previews.get(preview)
            if entry is None or email not in entry["emails"]:
                abort(404)
            delivery = getattr(entry["class"](request.args.to_dict()), email)()
            if not isinstance(delivery, MessageDelivery):
                raise ProgrammerError(
                    f"Mailer preview {preview}/{email} must return a MessageDelivery."
                )
            message = delivery.builder.build()
            bodies = {
                name: body.get_content()
                for name in ("html", "plain")
                if (body := message.get_body(preferencelist=(name,))) is not None
                and body.get_payload() is not None
            }
            part = request.args.get("part", "html" if "html" in bodies else "plain")
            if part not in ("html", "plain"):
                abort(404)
            links = {}
            for name in bodies:
                params = request.args.copy()
                params["part"] = name
                links[name] = (
                    url_for(".show", target=target)
                    + "?"
                    + urlencode(list(params.items(multi=True)))
                )
            return _render(
                "show.html",
                preview=preview,
                email=email,
                message=message,
                bodies=bodies,
                part=part,
                links=links,
            )

        @blueprint.after_request
        def protect(response):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; style-src 'unsafe-inline'; "
                "img-src 'self' data: https: http:; frame-src 'self'; "
                "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
            )
            return response

        app.register_blueprint(blueprint)


def _render(template, **context):
    return _templates.get_template(template).render(
        url_for=url_for,
        images=brand_images("logo-horizontal-dark", "favicon"),
        **context,
    )


def _discover_previews(app):
    previews = {}
    seen_paths = set()
    for configured_path in app.config.mailer.preview_paths:
        root = (app.project_root / configured_path).resolve()
        for path in sorted(root.rglob("*_preview.py")):
            if not path.is_file() or path in seen_paths:
                continue
            seen_paths.add(path)
            relative = path.relative_to(root)
            module_name = f"_flaskteroids_mail_preview_{id(app)}_{len(seen_paths)}"
            spec = spec_from_file_location(module_name, path)
            module = module_from_spec(spec)
            # Register source modules so Flask's development reloader watches them.
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            except BaseException:
                sys.modules.pop(module_name, None)
                raise
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if (
                    cls.__module__ != module_name
                    or cls is MailerPreview
                    or not issubclass(cls, MailerPreview)
                ):
                    continue
                name = "/".join(
                    (
                        *relative.parts[:-1],
                        inflector.underscore(cls.__name__.removesuffix("Preview")),
                    )
                )
                if name in previews:
                    raise ProgrammerError(f"Duplicate mailer preview {name!r}.")
                previews[name] = {
                    "class": cls,
                    "emails": sorted(
                        name
                        for name, method in vars(cls).items()
                        if not name.startswith("_") and inspect.isfunction(method)
                    ),
                }
    return dict(sorted(previews.items()))
