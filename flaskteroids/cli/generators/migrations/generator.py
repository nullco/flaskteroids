import os
from datetime import datetime
from flask import current_app
from alembic import command
from alembic.config import Config as AlembicConfig
from flaskteroids.cli.generators.migrations import cmd_parser


class Config(AlembicConfig):

    def get_template_directory(self):
        package_dir = os.path.abspath(os.path.dirname(__file__))
        return os.path.join(package_dir, 'templates')


def init():
    directory = 'migrations'
    config = Config()
    config.config_file_name = os.path.join(directory, 'alembic.ini')
    config.set_main_option('script_location', directory)
    template = 'default'
    command.init(config, directory, template=template, package=False)


def migration(cmd, args):
    directory = 'migrations'
    config = Config()
    config.config_file_name = os.path.join(directory, 'alembic.ini')
    config.set_main_option('revision_environment', 'true')
    config.set_main_option('script_location', directory)
    config.set_main_option('sqlalchemy.url', current_app.config['DATABASE_URL'])
    res = cmd_parser.parse(cmd, args)
    up_ops = res['parsed']['ops']
    command.revision(
        config,
        message=res['normalized_cmd'].replace('_', ' '),
        rev_id=datetime.now().strftime("%Y%m%d%H%M%S"),
        process_revision_directives=gen_process_revision_directives(up_ops, [])
    )


def _get_ops(cmd, args):
    up = cmd_parser.parse(cmd, args)['parsed']['ops']
    down = []
    return up, down


def gen_process_revision_directives(upgrade_ops, downgrade_ops):
    def fn(context, revision, directives):
        script, *_ = directives
        script.upgrade_ops.ops[:] = upgrade_ops
        script.downgrade_ops.ops[:] = downgrade_ops
    return fn
