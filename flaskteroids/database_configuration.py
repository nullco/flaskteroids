import os
import re
from pathlib import Path
from sqlalchemy.engine import URL
import yaml


_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


class DatabaseConfigurationError(RuntimeError):
    pass


def load_database_configuration(root, environment, environ=None):
    environ = os.environ if environ is None else environ
    path = Path(root, "config", "database.yml")
    if not path.exists():
        return None

    content = _interpolate(path.read_text(), environ)
    configurations = yaml.safe_load(content) or {}
    selected = configurations.get(str(environment))
    if selected is None:
        raise DatabaseConfigurationError(
            f"Database configuration for environment <{environment}> was not found in {path}"
        )

    if _is_multiple_database_configuration(selected):
        selected = selected.get("primary") or next(iter(selected.values()))
    if not isinstance(selected, dict):
        raise DatabaseConfigurationError(
            f"Database configuration for environment <{environment}> must be a mapping"
        )

    explicit_url = selected.get("url")
    environment_url = environ.get("DATABASE_URL")
    if "url" in selected:
        if not explicit_url:
            raise DatabaseConfigurationError("Explicit database URL is empty")
        database_url = explicit_url
    elif environment_url:
        database_url = environment_url
    else:
        database_url = _build_url(selected)

    return {
        "url": database_url,
        "selected": selected,
        "configurations": configurations,
    }


def _interpolate(content, environ):
    def replace(match):
        name, default = match.groups()
        if name in environ:
            return environ[name]
        if default is not None:
            return default
        return ""

    return _ENV_PATTERN.sub(replace, content)


def _is_multiple_database_configuration(configuration):
    if not isinstance(configuration, dict) or not configuration:
        return False
    database_keys = {
        "adapter",
        "database",
        "url",
        "host",
        "port",
        "username",
        "password",
        "pool",
    }
    return not database_keys.intersection(configuration) and all(
        isinstance(value, dict) for value in configuration.values()
    )


def _build_url(configuration):
    adapter = configuration.get("adapter")
    database = configuration.get("database")
    if not adapter:
        raise DatabaseConfigurationError("Database adapter is missing")
    if not database:
        raise DatabaseConfigurationError("Database name is missing")

    if adapter in {"sqlite", "sqlite3"}:
        if database == ":memory:":
            return "sqlite:///:memory:"
        return f"sqlite:///{database}"

    driver = {
        "postgres": "postgresql",
        "postgresql": "postgresql",
        "mysql": "mysql",
        "mysql2": "mysql",
    }.get(adapter, adapter)
    url = URL.create(
        drivername=driver,
        username=configuration.get("username"),
        password=configuration.get("password"),
        host=configuration.get("host"),
        port=configuration.get("port"),
        database=database,
    )
    return url.render_as_string(hide_password=False)
