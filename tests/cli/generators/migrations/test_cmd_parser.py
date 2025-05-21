import pytest
from flaskteroids.cli.generators.migrations import cmd_parser
from alembic.operations import ops
import sqlalchemy as sa
from datetime import datetime, timezone


@pytest.mark.parametrize('cmd, args, expected', [
    (
        'CreateProducts',
        ('name:str',),
        {
            'normalized_cmd': 'create_products',
            'parsed': {
                'cmd': 'create_table',
                'ops': {
                    'up': [
                        ops.CreateTableOp(
                            'products',
                            [
                                sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
                                sa.Column('created_at', sa.DateTime(), default=lambda: datetime.now(timezone.utc)),
                                sa.Column(
                                    'updated_at',
                                    sa.DateTime(),
                                    default=lambda: datetime.now(timezone.utc),
                                    onupdate=lambda: datetime.now(timezone.utc),
                                ),
                                sa.Column('name', sa.String(255), nullable=True)
                            ]
                        )

                    ]
                }
            }
        }
    ),
    (
        'CreateProducts',
        ('name:str', 'user:references'),
        {
            'normalized_cmd': 'create_products',
            'parsed': {
                'cmd': 'create_table',
                'ops': {
                    'up': [
                        ops.CreateTableOp(
                            'products',
                            [
                                sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
                                sa.Column('created_at', sa.DateTime(), default=lambda: datetime.now(timezone.utc)),
                                sa.Column(
                                    'updated_at',
                                    sa.DateTime(),
                                    default=lambda: datetime.now(timezone.utc),
                                    onupdate=lambda: datetime.now(timezone.utc),
                                ),
                                sa.Column('name', sa.String(255), nullable=True),
                                sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False)
                            ]
                        )

                    ]
                }
            }
        }
    ),
    (
        'CreateProducts',
        ('name:str', 'user:belongs_to'),
        {
            'normalized_cmd': 'create_products',
            'parsed': {
                'cmd': 'create_table',
                'ops': {
                    'up': [
                        ops.CreateTableOp(
                            'products',
                            [
                                sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
                                sa.Column('created_at', sa.DateTime(), default=lambda: datetime.now(timezone.utc)),
                                sa.Column(
                                    'updated_at',
                                    sa.DateTime(),
                                    default=lambda: datetime.now(timezone.utc),
                                    onupdate=lambda: datetime.now(timezone.utc),
                                ),
                                sa.Column('name', sa.String(255), nullable=True),
                                sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False)
                            ]
                        )

                    ]
                }
            }
        }
    ),
])
def test_create_table(cmd, args, expected):
    res = cmd_parser.parse(cmd, args)
    assert res['normalized_cmd'] == expected['normalized_cmd']
    assert res['parsed']['cmd'] == expected['parsed']['cmd']
    ops = res['parsed']['ops']['up']
    expected_ops = expected['parsed']['ops']['up']
    for op, expected_op in zip(ops, expected_ops):
        assert type(op) is type(expected_op)
        assert op.table_name == expected_op.table_name
        assert len(op.columns) == len(expected_op.columns)
        for oc, eoc in zip(op.columns, expected_op.columns):
            assert oc.name == eoc.name
            # TODO: need to check how to assert for column type
            assert oc.nullable == eoc.nullable
            assert len(oc.foreign_keys) == len(eoc.foreign_keys)


@pytest.mark.parametrize('cmd, args, expected', [
    (
        'AddPriceToProducts',
        ('price:float',),
        {
            'normalized_cmd': 'add_price_to_products',
            'parsed': {
                'cmd': 'add_columns_to_table',
                'ops': {
                    'up': [
                        ops.AddColumnOp(
                            'products',
                            sa.Column('price', sa.Float(), nullable=True)
                        )
                    ]
                }
            }
        }
    ),
    (
        'AddPriceAndTotalToProducts',
        ('price:float', 'total:int!'),
        {
            'normalized_cmd': 'add_price_and_total_to_products',
            'parsed': {
                'cmd': 'add_columns_to_table',
                'ops': {
                    'up': [
                        ops.AddColumnOp(
                            'products',
                            sa.Column('price', sa.Float(), nullable=True)
                        ),
                        ops.AddColumnOp(
                            'products',
                            sa.Column('total', sa.Integer(), nullable=True)
                        )

                    ]
                }
            }
        }
    )
])
def test_add_columns_to_table(cmd, args, expected):
    res = cmd_parser.parse(cmd, args)
    assert res['normalized_cmd'] == expected['normalized_cmd']
    assert res['parsed']['cmd'] == expected['parsed']['cmd']
    ops = res['parsed']['ops']['up']
    expected_ops = expected['parsed']['ops']['up']
    for op, expected_op in zip(ops, expected_ops):
        assert type(op) is type(expected_op)
        assert op.table_name == expected_op.table_name
        assert op.column.name == expected_op.column.name


@pytest.mark.parametrize('cmd, args, expected', [
    (
        'RemovePriceFromProducts',
        ('price',),
        {
            'normalized_cmd': 'remove_price_from_products',
            'parsed': {
                'cmd': 'remove_columns_from_table',
                'ops': {'up': [ops.DropColumnOp('products', 'price')]}
            }
        }
    ),
    (
        'RemovePriceAndTotalFromProducts',
        ('price', 'total'),
        {
            'normalized_cmd': 'remove_price_and_total_from_products',
            'parsed': {
                'cmd': 'remove_columns_from_table',
                'ops': {
                    'up': [
                        ops.DropColumnOp('products', 'price'),
                        ops.DropColumnOp('products', 'total'),
                    ]
                }
            }
        }
    )
])
def test_remove_columns_from_table(cmd, args, expected):
    res = cmd_parser.parse(cmd, args)
    assert res['normalized_cmd'] == expected['normalized_cmd']
    assert res['parsed']['cmd'] == expected['parsed']['cmd']
    ops = res['parsed']['ops']['up']
    expected_ops = expected['parsed']['ops']['up']
    for op, expected_op in zip(ops, expected_ops):
        assert type(op) is type(expected_op)
        assert op.table_name == expected_op.table_name
        assert op.column_name == expected_op.column_name


def test_invalid_command():
    with pytest.raises(Exception):
        cmd_parser.parse('InvalidCommand', *[])
