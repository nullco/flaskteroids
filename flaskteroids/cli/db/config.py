import os
from flask import current_app
from alembic.config import Config as AlembicConfig

_directory = os.path.join('db', 'migrate')


class Config(AlembicConfig):

    def get_template_directory(self):
        package_dir = os.path.abspath(os.path.dirname(__file__))
        return os.path.join(package_dir, 'templates')


def get_config():
    config = Config()
    config.config_file_name = os.path.join(_directory, 'alembic.ini')
    config.set_main_option('revision_environment', 'true')
    config.set_main_option('script_location', _directory)
    config.set_main_option('sqlalchemy.url', current_app.config['DB']['SQLALCHEMY_URL'])
    return config
