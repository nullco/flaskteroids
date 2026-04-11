from datetime import datetime
from alembic import command
from flaskteroids.cli.generators.migrations import cmd_parser
from flaskteroids.cli.db.config import get_config


def generate(cmd, args):
    config = get_config()
    res = cmd_parser.parse(cmd, args)
    up_ops = res['parsed']['ops']['up']
    down_ops = res['parsed']['ops']['down']
    command.revision(
        config,
        message=res['normalized_cmd'].replace('_', ' '),
        rev_id=datetime.now().strftime("%Y%m%d%H%M%S%f"),
        process_revision_directives=_gen_process_revision_directives(up_ops, down_ops)
    )


def _gen_process_revision_directives(upgrade_ops, downgrade_ops):
    def fn(context, revision, directives):
        script, *_ = directives
        script.upgrade_ops.ops[:] = upgrade_ops
        script.downgrade_ops.ops[:] = downgrade_ops
    return fn
