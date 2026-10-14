import os

from alembic import command
from alembic.config import Config as AlembicConfig
from flask import current_app

_directory = os.path.join("db", "migrate")


class Config(AlembicConfig):
    def get_template_directory(self):
        package_dir = os.path.abspath(os.path.dirname(__file__))
        return os.path.join(package_dir, "templates")


def initialize_migrations(directory):
    """Initialize canonical migration resources without booting an application."""
    config = Config()
    config.config_file_name = os.path.join(directory, "alembic.ini")
    command.init(config, str(directory), template="default", package=False)


def get_config():
    config = Config()
    config.config_file_name = os.path.join(_directory, "alembic.ini")
    config.set_main_option("revision_environment", "true")
    config.set_main_option("script_location", _directory)
    config.set_main_option("sqlalchemy.url", current_app.database_url)
    return config
