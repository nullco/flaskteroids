import os
from alembic import command
from alembic.operations import ops
from alembic.config import Config as AlembicConfig
import sqlalchemy as sa


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
    config.set_main_option('script_location', directory)
    config.set_main_option('sqlalchemy.url', 'sqlite:///database.db')
    up_ops, down_ops = _get_ops(cmd, args)
    command.revision(config, process_revision_directives=gen_process_revision_directives(up_ops, down_ops))


def _get_ops(cmd, args):
    up = [
        # ops.CreateTableOp(
        #     'organization',
        #     [
        #         sa.Column('id', sa.Integer(), primary_key=True),
        #         sa.Column('name', sa.String(50), nullable=False)
        #     ]
        # )
    ]
    down = [
        # ops.DropTableOp('organization')
    ]
    return up, down


def gen_process_revision_directives(upgrade_ops, downgrade_ops):
    def fn(context, revision, directives):
        script, *_ = directives
        script.upgrade_ops.ops[:] = upgrade_ops
        script.downgrade_ops.ops[:] = downgrade_ops
    return fn
