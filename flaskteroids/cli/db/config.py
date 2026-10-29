import os
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from flask import current_app

from flaskteroids.cli.db.output import migration_output

_directory = os.path.join("db", "migrate")


class Config(AlembicConfig):
    def get_template_directory(self):
        package_dir = os.path.abspath(os.path.dirname(__file__))
        return os.path.join(package_dir, "templates")


def initialize_migrations(directory):
    """Initialize canonical resources silently; the generator owns user-facing output."""
    config = Config()
    config.config_file_name = os.path.join(directory, "alembic.ini")
    # Alembic emits its own progress and a configuration prompt that does not
    # apply to generated apps, whose database settings live in config/database.yml.
    with migration_output():
        command.init(config, str(directory), template="default", package=False)


def get_config():
    config = Config()
    directory = Path(current_app.project_root) / _directory
    config.config_file_name = str(directory / "alembic.ini")
    config.set_main_option("revision_environment", "true")
    config.set_main_option("script_location", str(directory).replace("%", "%%"))
    url = current_app.database_url
    if not isinstance(url, str):
        url = url.render_as_string(hide_password=False)
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config
