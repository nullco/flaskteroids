import re
from flaskteroids.cli.generators import cmd_parser
import sqlalchemy as sa
from alembic.operations import ops
from datetime import datetime, timezone
from flaskteroids.str_utils import pluralize


_column_types = {
    'int': sa.Integer,
    'str': lambda: sa.String(255),
    'text': sa.Text,
    'float': sa.Float,
    'bool': sa.Boolean,
    'json': sa.JSON
}

_column_types_pattern = fr'{"|".join(k for k in _column_types.keys())}'

_column_pattern = re.compile(fr'^([a-z_]+):({_column_types_pattern})(!?)$')
_reference_pattern = re.compile(r'^([a-z_]+):(references|belongs_to)$')


class _CreateTableCommand:
    pattern = re.compile(r'create_([a-z]+)')
    args = {
        'column': _column_pattern,
        'reference': _reference_pattern
    }

    @classmethod
    def parse(cls, cmd, args):
        matcher = cmd_parser.CommandArgsMatcher(cls.pattern, cls.args)
        cmd_match = matcher.match_cmd(cmd)
        args_matches = matcher.match_args(args)
        return {
            'cmd': 'create_table',
            'ops': {
                'up': [
                    ops.CreateTableOp(
                        cmd_match.group(1),
                        [
                            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
                            sa.Column('created_at', sa.DateTime(), default=lambda: datetime.now(timezone.utc)),
                            sa.Column(
                                'updated_at',
                                sa.DateTime(),
                                default=lambda: datetime.now(timezone.utc),
                                onupdate=lambda: datetime.now(timezone.utc),
                            ),
                            *[
                                sa.Column(
                                    name=am.group(1),
                                    type_=_column_types[am.group(2)](),
                                    nullable=not bool(am.group(3))
                                )
                                for am in args_matches.get('column', [])
                            ],
                            *[
                                sa.Column(
                                    f'{am.group(1)}_id',
                                    sa.Integer(),
                                    sa.ForeignKey(f'{pluralize(am.group(1))}.id'),
                                    nullable=False
                                )
                                for am in args_matches.get('reference', [])
                            ]
                        ],
                        _namespace_metadata=sa.MetaData()
                    )
                ],
                'down': [
                    ops.DropTableOp(cmd_match.group(1))
                ]
            }
        }


class _DropTableCommand:
    pattern = re.compile(r'create_([a-z]+)')

    @classmethod
    def parse(cls, cmd, _):
        matcher = cmd_parser.CommandArgsMatcher(cls.pattern)
        match = matcher.match_cmd(cmd)
        return {
            'cmd': 'drop_table',
            'ops': {
                'up': [
                    ops.DropTableOp(match.group(1))
                ],
                'down': []
            }
        }


class _AddColumnsToTableCommand:
    pattern = re.compile(r'add_([a-z_]+)_to_([a-z]+)')
    args = {
        'column': _column_pattern,
        'reference': _reference_pattern
    }

    @classmethod
    def parse(cls, cmd, args):
        matcher = cmd_parser.CommandArgsMatcher(cls.pattern, cls.args)
        cmd_match = matcher.match_cmd(cmd)
        args_matches = matcher.match_args(args)
        return {
            'cmd': 'add_columns_to_table',
            'ops': {
                'up': [
                    ops.AddColumnOp(
                        cmd_match.group(2),
                        sa.Column(
                            name=am.group(1),
                            type_=_column_types[am.group(2)](),
                            nullable=not bool(am.group(3))
                        )
                    )
                    for am in args_matches.get('column', [])
                ],
                'down': [
                    ops.DropColumnOp(
                        cmd_match.group(2),
                        am.group(1)
                    )
                    for am in args_matches.get('column', [])
                ]
            }
        }


class _RemoveColumnsFromTableCommand:
    pattern = re.compile(r'remove_([a-z_]+)_from_([a-z]+)')
    args = {
        'remove_column': re.compile(fr'^([a-z_]+)(:({_column_types_pattern})(!?))?$')
    }

    @classmethod
    def parse(cls, cmd, args):
        matcher = cmd_parser.CommandArgsMatcher(cls.pattern, cls.args)
        cmd_match = matcher.match_cmd(cmd)
        args_matches = matcher.match_args(args)
        return {
            'cmd': 'remove_columns_from_table',
            'ops': {
                'up': [
                    ops.DropColumnOp(
                        cmd_match.group(2),
                        am.group(1)
                    )
                    for am in args_matches.get('remove_column', [])
                ],
                'down': [
                    ops.AddColumnOp(
                        cmd_match.group(2),
                        sa.Column(
                            name=am.group(1),
                            type_=_column_types[am.group(3)](),
                            nullable=not bool(am.group(4))
                        )
                    )
                    for am in args_matches.get('remove_column', []) if am.group(2)
                ],
            }
        }


_cmds = [
    _CreateTableCommand,
    _DropTableCommand,
    _AddColumnsToTableCommand,
    _RemoveColumnsFromTableCommand,
]


def parse(cmd, args):
    return cmd_parser.parse(cmd, args, _cmds)
