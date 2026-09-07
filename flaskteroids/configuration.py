from flask.config import Config as FlaskConfig


class Options:
    def __init__(self, values=None, *, autovivify=False):
        object.__setattr__(self, "_values", {})
        object.__setattr__(self, "_autovivify", autovivify)
        for key, value in (values or {}).items():
            setattr(self, key, value)

    def __getattr__(self, name):
        values = object.__getattribute__(self, "_values")
        if name in values:
            return values[name]
        if object.__getattribute__(self, "_autovivify"):
            value = Options(autovivify=True)
            values[name] = value
            return value
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if isinstance(value, dict):
            value = Options(value)
        self._values[name] = value

    def __getitem__(self, name):
        return self._values[name]

    def __setitem__(self, name, value):
        setattr(self, name, value)

    def get(self, name, default=None):
        return self._values.get(name, default)

    def to_dict(self):
        return {
            key: value.to_dict() if isinstance(value, Options) else value
            for key, value in self._values.items()
        }


class Configuration(FlaskConfig):
    def __init__(self, root_path, defaults=None):
        super().__init__(root_path, defaults)
        self._defaults_version = None
        self.paths = Options(
            {
                "models": "app.models",
                "views": "app/views",
                "controllers": "app.controllers",
                "routes": "config.routes",
                "jobs": "app.jobs",
                "mailers": "app.mailers",
                "initializers": "config/initializers",
            }
        )
        self.active_job = Options(
            {
                "broker_url": "sqla+sqlite:///storage/jobs_database.db",
                "result_backend": None,
                "additional_config": {},
            }
        )
        self.action_mailer = Options(
            {
                "perform_deliveries": False,
                "smtp_settings": {},
                "default_options": {"from_": "no-reply@flaskteroids.me"},
            }
        )
        self.action_controller = Options(
            {
                "perform_caching": False,
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
