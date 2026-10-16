import pytest

import flaskteroids.cli.db.commands as db


@pytest.fixture
def command(mocker):
    mocker.patch.object(db, "dump_schema")
    return mocker.patch.object(db, "command")


@pytest.mark.parametrize(
    "task, operation",
    [("init", "init"), ("migrate", "upgrade"), ("rollback", "downgrade")],
)
def test_database_command_dispatches_to_alembic(cli_runner, command, task, operation):
    result = cli_runner.invoke(args=f"db:{task}")

    assert result.exit_code == 0, result.output
    getattr(command, operation).assert_called_once()
