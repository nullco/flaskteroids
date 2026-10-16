import pytest
import sqlalchemy as sa
from alembic.operations import ops

from flaskteroids.cli.generators.migrations import cmd_parser


@pytest.mark.parametrize("reference", [None, "references", "belongs_to"])
def test_parser_builds_create_table_command(reference):
    arguments = ["name:str"]
    if reference:
        arguments.append(f"user:{reference}")
    result = cmd_parser.parse("CreateProducts", arguments)
    assert result["normalized_cmd"] == "create_products"
    assert result["parsed"]["cmd"] == "create_table"
    operation = result["parsed"]["ops"]["up"][0]
    assert isinstance(operation, ops.CreateTableOp)
    assert operation.table_name == "products"
    columns = {column.name: column for column in operation.columns}
    expected_names = {"id", "created_at", "updated_at", "name"}
    if reference:
        expected_names.add("user_id")
    assert set(columns) == expected_names
    assert columns["id"].primary_key
    assert columns["id"].autoincrement is True
    assert isinstance(columns["id"].type, sa.Integer)
    assert isinstance(columns["name"].type, sa.String)
    assert columns["name"].type.length == 255
    assert columns["name"].nullable
    for name in ("created_at", "updated_at"):
        assert isinstance(columns[name].type, sa.DateTime)
        assert columns[name].default is None
        assert columns[name].onupdate is None
    if reference:
        assert not columns["user_id"].nullable
        assert {key.target_fullname for key in columns["user_id"].foreign_keys} == {
            "users.id"
        }


@pytest.mark.parametrize(
    "cmd, expected",
    [
        (
            "DropProducts",
            {
                "normalized_cmd": "drop_products",
                "parsed": {
                    "cmd": "drop_table",
                    "ops": {"up": [ops.DropTableOp("products")]},
                },
            },
        ),
    ],
)
def test_parser_builds_drop_table_command(cmd, expected):
    res = cmd_parser.parse(cmd, None)
    assert res["normalized_cmd"] == expected["normalized_cmd"]
    assert res["parsed"]["cmd"] == expected["parsed"]["cmd"]
    ops = res["parsed"]["ops"]["up"]
    expected_ops = expected["parsed"]["ops"]["up"]
    for op, expected_op in zip(ops, expected_ops, strict=False):
        assert type(op) is type(expected_op)
        assert op.table_name == expected_op.table_name


@pytest.mark.parametrize(
    "cmd, args, expected",
    [
        (
            "AddPriceToProducts",
            ("price:float",),
            {
                "normalized_cmd": "add_price_to_products",
                "parsed": {
                    "cmd": "add_columns_to_table",
                    "ops": {
                        "up": [
                            ops.ModifyTableOps(
                                "products",
                                ops=[
                                    ops.AddColumnOp(
                                        "products",
                                        sa.Column("price", sa.Float(), nullable=True),
                                    )
                                ],
                            )
                        ]
                    },
                },
            },
        ),
        (
            "AddPriceAndTotalToProducts",
            ("price:float", "total:int!"),
            {
                "normalized_cmd": "add_price_and_total_to_products",
                "parsed": {
                    "cmd": "add_columns_to_table",
                    "ops": {
                        "up": [
                            ops.ModifyTableOps(
                                "products",
                                ops=[
                                    ops.AddColumnOp(
                                        "products",
                                        sa.Column("price", sa.Float(), nullable=True),
                                    ),
                                    ops.AddColumnOp(
                                        "products",
                                        sa.Column("total", sa.Integer(), nullable=True),
                                    ),
                                ],
                            )
                        ]
                    },
                },
            },
        ),
    ],
)
def test_parser_builds_add_column_commands(cmd, args, expected):
    res = cmd_parser.parse(cmd, args)
    assert res["normalized_cmd"] == expected["normalized_cmd"]
    assert res["parsed"]["cmd"] == expected["parsed"]["cmd"]
    ops = res["parsed"]["ops"]["up"]
    expected_ops = expected["parsed"]["ops"]["up"]
    for op, expected_op in zip(ops, expected_ops, strict=False):
        assert type(op) is type(expected_op)
        assert op.table_name == expected_op.table_name


@pytest.mark.parametrize(
    "cmd, args, expected",
    [
        (
            "RemovePriceFromProducts",
            ("price",),
            {
                "normalized_cmd": "remove_price_from_products",
                "parsed": {
                    "cmd": "remove_columns_from_table",
                    "ops": {"up": [ops.DropColumnOp("products", "price")]},
                },
            },
        ),
        (
            "RemovePriceAndTotalFromProducts",
            ("price", "total"),
            {
                "normalized_cmd": "remove_price_and_total_from_products",
                "parsed": {
                    "cmd": "remove_columns_from_table",
                    "ops": {
                        "up": [
                            ops.DropColumnOp("products", "price"),
                            ops.DropColumnOp("products", "total"),
                        ]
                    },
                },
            },
        ),
    ],
)
def test_parser_builds_remove_column_commands(cmd, args, expected):
    res = cmd_parser.parse(cmd, args)
    assert res["normalized_cmd"] == expected["normalized_cmd"]
    assert res["parsed"]["cmd"] == expected["parsed"]["cmd"]
    ops = res["parsed"]["ops"]["up"]
    expected_ops = expected["parsed"]["ops"]["up"]
    for op, expected_op in zip(ops, expected_ops, strict=False):
        assert type(op) is type(expected_op)
        assert op.table_name == expected_op.table_name
        assert op.column_name == expected_op.column_name


@pytest.mark.parametrize(
    "cmd, args",
    [
        ("InvalidCommand", []),
        ("AddCompletedAndPriorityToTodos", ["completed:boolean", "priority:wronnnngg"]),
    ],
)
def test_parser_rejects_invalid_commands(cmd, args):
    with pytest.raises(ValueError):
        cmd_parser.parse(cmd, args)
