from collections import defaultdict
import re
from flaskteroids.cli.generators import cmd_parser
import sqlalchemy as sa
from alembic.operations import ops
from datetime import datetime, timezone


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
_reference_pattern = re.compile(r'^([a-z_]+):references$')


class _CommandArgsMatcher:

    def __init__(self, cmd_pattern, args_patterns):
        self._cmd_pattern = cmd_pattern
        self._args_patterns = args_patterns

    def match(self, cmd, args):
        match = self._cmd_pattern.match(cmd)
        if match:
            if not self._args_patterns and args:
                raise Exception('Arguments not expected')
            args_matches = defaultdict(lambda: [])
            for arg in args:
                for k, p in self._args_patterns.items():
                    amatch = p.match(arg)
                    if amatch:
                        args_matches[k].append(amatch)
            if not args_matches:
                raise Exception('Argument not matching expected format')
            return match, args_matches


class _CreateTableCommand:
    pattern = re.compile(r'create_([a-z]+)')
    args = {
        'column': _column_pattern,
        'reference': _reference_pattern
    }

    @classmethod
    def parse(cls, cmd, args):
        matcher = _CommandArgsMatcher(cls.pattern, cls.args)
        match = matcher.match(cmd, args)
        if match:
            cmd_match, args_matches = match
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
                                ]
                            ],
                        )
                    ],
                    'down': [
                        ops.DropTableOp(cmd_match.group(1))
                    ]
                }
            }


class _DropTableCommand:
    pattern = re.compile(r'create_([a-z]+)')
    args = None

    @classmethod
    def parse(cls, cmd, args):
        matcher = _CommandArgsMatcher(cls.pattern, cls.args)
        match = matcher.match(cmd, args)
        if match:
            cmd_match, _ = match
            return {
                'cmd': 'drop_table',
                'ops': {
                    'up': [
                        ops.DropTableOp(cmd_match.group(1))
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
        matcher = _CommandArgsMatcher(cls.pattern, cls.args)
        match = matcher.match(cmd, args)
        if match:
            cmd_match, args_matches = match
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
        matcher = _CommandArgsMatcher(cls.pattern, cls.args)
        match = matcher.match(cmd, args)
        if match:
            cmd_match, args_matches = match
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
