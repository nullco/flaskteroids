import importlib.util
import os
import secrets
import sys
from pathlib import Path
from flask import Flask
from flaskteroids.configuration import Configuration
from flaskteroids.credentials import Credentials, CredentialsError
from flaskteroids.database_configuration import load_database_configuration


class Environment(str):
    @property
    def name(self):
        return str(self)

    @property
    def development(self):
        return self == "development"

    @property
    def test(self):
        return self == "test"

    @property
    def production(self):
        return self == "production"


class Application(Flask):
    config_class = Configuration
    root = None

    @classmethod
    def initialize(cls, *, environment=None, root_path=None):
        return cls(environment=environment, root_path=root_path)

    def __init__(self, *, environment=None, root_path=None):
        project_root = Path(root_path or self._project_root()).resolve()
        super().__init__(
            self.__class__.__module__, root_path=str(project_root), template_folder=None
        )
        self.project_root = project_root
        self.env = Environment(
            environment
            or os.environ.get("FLASKTEROIDS_ENV")
            or os.environ.get("FLASK_ENV")
            or "development"
        )
        self.credentials = Credentials(project_root, self.env)
        self.database_url = "sqlite:///storage/database.db"
        self.database_configurations = {}

        self.configure(self.config)
        self._configure_environment()
        self._configure_database()
        self._configure_secret_key()
        self.config.finalize()
        self.template_folder = str(project_root / self.config.paths.views)
        self.extensions["flaskteroids.application"] = self

        from flaskteroids.app import finalize_app, initialize_app

        initialize_app(self)
        self._run_initializers()
        finalize_app(self)

    def configure(self, config):
        config.load_defaults("0.1")

    def _project_root(self):
        if self.root:
            return self.root
        module = sys.modules.get(self.__class__.__module__)
        module_path = getattr(module, "__file__", None)
        if module_path:
            path = Path(module_path).resolve().parent
            if path.name == "config":
                return path.parent
        return Path.cwd()

    def _configure_environment(self):
        path = self.project_root / "config" / "environments" / f"{self.env}.py"
        if not path.exists():
            return
        module = _load_module(path, f"_flaskteroids_environment_{id(self)}")
        configure = getattr(module, "configure", None)
        if configure:
            configure(self.config)

    def _configure_database(self):
        database = load_database_configuration(self.project_root, self.env)
        if not database:
            return
        self.database_url = database["url"]
        self.database_configurations = database["configurations"]

    def _configure_secret_key(self):
        if self.config.require_master_key:
            if not self.credentials.content_path.exists():
                raise CredentialsError(
                    f"Encrypted credentials were not found at {self.credentials.content_path}"
                )
            if not self.credentials.key():
                raise CredentialsError(
                    "Missing credentials key. Set FLASKTEROIDS_MASTER_KEY or provide the key file."
                )

        secret_key_base = (
            os.environ.get("SECRET_KEY_BASE") or self.config.secret_key_base
        )
        if not secret_key_base and self.credentials.content_path.exists():
            secret_key_base = self.credentials.get("secret_key_base")
        if not secret_key_base:
            if self.env.production:
                raise CredentialsError(
                    "Missing secret_key_base. Add it to credentials or set SECRET_KEY_BASE."
                )
            secret_key_base = secrets.token_hex(64)
        self.config.secret_key_base = secret_key_base

    def _run_initializers(self):
        path = self.project_root / self.config.paths.initializers
        if not path.exists():
            return
        with self.app_context():
            for initializer in sorted(path.glob("*.py")):
                if initializer.name.startswith("_"):
                    continue
                _load_module(
                    initializer,
                    f"_flaskteroids_initializer_{initializer.stem}_{id(self)}",
                )


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise ImportError(f"Unable to load configuration file {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
