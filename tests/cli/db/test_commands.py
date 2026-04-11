import pytest
import flaskteroids.cli.db.commands as db


@pytest.fixture
def command(mocker):
    return mocker.patch.object(db, 'command')


def test_init(cli_runner, command):
    cli_runner.invoke(args='db:init')
    command.init.assert_called()


def test_migrate(cli_runner, command):
    cli_runner.invoke(args='db:migrate')
    command.upgrade.assert_called()


def test_rollback(cli_runner, command):
    cli_runner.invoke(args='db:rollback')
    command.downgrade.assert_called()
