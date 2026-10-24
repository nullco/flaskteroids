from collections.abc import Mapping
from typing import Any

from flask.config import Config as FlaskConfig

from flaskteroids.assets import OUTPUT_PATH, SOURCE_PATH
from flaskteroids.jobs.adapters import CeleryQueueAdapter
from flaskteroids.mail.delivery_methods import SMTPDeliveryMethod


class Options:
    def __init__(
        self, values: Mapping[str, Any] | None = None, *, autovivify: bool = False
    ) -> None:
        object.__setattr__(self, "_values", {})
        object.__setattr__(self, "_autovivify", autovivify)
        for key, value in (values or {}).items():
            setattr(self, key, value)

    def __getattr__(self, name: str) -> Any:
        values = object.__getattribute__(self, "_values")
        if name in values:
            return values[name]
        if object.__getattribute__(self, "_autovivify"):
            value = Options(autovivify=True)
            values[name] = value
            return value
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if isinstance(value, dict):
            value = Options(value)
        self._values[name] = value

    def __getitem__(self, name: str) -> Any:
        return self._values[name]

    def __setitem__(self, name: str, value: Any) -> None:
        setattr(self, name, value)

    def get(self, name: str, default: Any = None) -> Any:
        return self._values.get(name, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            key: value.to_dict() if isinstance(value, Options) else value
            for key, value in self._values.items()
        }


class Configuration(FlaskConfig):
    paths: Options
    jobs: Options

    def __init__(self, root_path, defaults=None):
        super().__init__(root_path, defaults)
        self._defaults_version = None
        self.paths = Options(
            {
                "models": "app.models",
                "views": "app/views",
                "controllers": "app.controllers",
                "helpers": "app.helpers",
                "routes": "config.routes",
                "jobs": "app.jobs",
                "mailers": "app.mailers",
                "initializers": "config/initializers",
                "locales": "config/locales",
            }
        )
        self.assets = Options(
            {
                "source_path": SOURCE_PATH,
                "output_path": OUTPUT_PATH,
                "prefix": "/assets",
                "serve": True,
            }
        )
        self.jobs = Options(
            {
                "broker_url": "sqla+sqlite:///storage/jobs_database.db",
                "result_backend": None,
                "additional_config": {},
                "queue_adapter": CeleryQueueAdapter,
            }
        )
        self.i18n = Options(
            {
                "default_locale": "en",
                "available_locales": ["en"],
                "fallbacks": False,
                "raise_on_missing_translations": False,
                "pluralization_rules": {},
            }
        )
        self.database_tasks = Options({"maintenance_database": "postgres"})
        self.attachments = Options(
            {
                "service": None,
                "max_upload_size": None,
                "urls_expire_in": None,
                "service_urls_expire_in": 300,
                "resolve_model_to_route": "redirect",
                "content_types_to_serve_as_binary": [
                    "text/html",
                    "image/svg+xml",
                    "application/postscript",
                    "application/x-shockwave-flash",
                    "text/xml",
                    "application/xml",
                    "application/xhtml+xml",
                    "application/mathml+xml",
                    "text/cache-manifest",
                ],
                "content_types_allowed_inline": [
                    "image/webp",
                    "image/avif",
                    "image/png",
                    "image/gif",
                    "image/jpeg",
                    "image/tiff",
                    "image/bmp",
                    "image/vnd.adobe.photoshop",
                    "image/vnd.microsoft.icon",
                    "application/pdf",
                ],
                "draw_routes": True,
                "authorize": None,
            }
        )
        self.encryption = Options(
            {
                "primary_key": None,
                "deterministic_key": None,
                "support_unencrypted_data": False,
            }
        )
        self.rich_text = Options(
            {
                "authorize_upload": None,
                "upload_token_expires_in": 3600,
            }
        )
        self.action_mailer = Options(
            {
                "perform_deliveries": False,
                "delivery_method": SMTPDeliveryMethod,
                "smtp_settings": {},
                "default_options": {"from_": "no-reply@flaskteroids.me"},
            }
        )
        self.action_controller = Options(
            {
                "perform_caching": False,
                "include_all_helpers": True,
                "allow_forgery_protection": True,
            }
        )
        self.x = Options(autovivify=True)
        self.require_master_key = False
        self.secret_key_base = None
        self.eager_load = False
        self.enable_reloading = False
        self.consider_all_requests_local = False

    def load_defaults(self, version):
        self._defaults_version = str(version)

    @property
    def defaults_version(self):
        return self._defaults_version

    def finalize(self):
        self["SECRET_KEY"] = self.secret_key_base
        self["TEMPLATES_AUTO_RELOAD"] = self.enable_reloading
        self["PROPAGATE_EXCEPTIONS"] = self.consider_all_requests_local
