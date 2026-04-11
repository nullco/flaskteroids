import re
from flaskteroids.cli.generators import cmd_parser
import sqlalchemy as sa
from alembic.operations import ops
from datetime import datetime, timezone
from flaskteroids.inflector import inflector
from flaskteroids.cli.generators.fields import fields, field_types_pattern, field_pattern, association_pattern


class _CreateTableCommand:
    pattern = re.compile(r'create_([a-z_]+)')
    args = {
        'column': field_pattern,
        'reference': association_pattern
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
                                    type_=fields.get(am.group(2)).new_column(),
                                    nullable=not bool(am.group(3))
                                )
                                for am in args_matches.get('column', [])
                            ],
                            *[
                                sa.Column(
                                    f'{am.group(1)}_id',
                                    sa.Integer(),
                                    sa.ForeignKey(f'{inflector.pluralize(am.group(1))}.id'),
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
    pattern = re.compile(r'drop_([a-z_]+)')

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
    pattern = re.compile(r'add_([a-z_]+)_to_([a-z_]+)')
    args = {
        'column': field_pattern,
        'reference': association_pattern
    }

    @classmethod
    def parse(cls, cmd, args):
        matcher = cmd_parser.CommandArgsMatcher(cls.pattern, cls.args)
        cmd_match = matcher.match_cmd(cmd)
        args_matches = matcher.match_args(args)

        def _add_references():
            references = []
            for am in args_matches.get('reference', []):
                references.append(
                    ops.AddColumnOp(
                        cmd_match.group(2),
                        sa.Column(
                            name=f'{am.group(1)}_id',
                            type_=sa.Integer(),
                            nullable=False
                        )
                    )
                )
                references.append(
                    ops.CreateForeignKeyOp(
                        f'fk_{cmd_match.group(2)}_{inflector.pluralize(am.group(1))}',
                        cmd_match.group(2),
                        inflector.pluralize(am.group(1)),
                        [f'{am.group(1)}_id'],
                        ['id']
                    )
                )
            return references

        return {
            'cmd': 'add_columns_to_table',
            'ops': {
                'up': [
                    ops.ModifyTableOps(
                        cmd_match.group(2),
                        ops=[
                            *[
                                ops.AddColumnOp(
                                    cmd_match.group(2),
                                    sa.Column(
                                        name=am.group(1),
                                        type_=fields.get(am.group(2)).new_column(),
                                        nullable=not bool(am.group(3))
                                    )
                                )
                                for am in args_matches.get('column', [])
                            ],
                            *_add_references()
                        ],
                    )
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
        'remove_column': re.compile(fr'^([a-z_]+)(:({field_types_pattern})(!?))?$')
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
