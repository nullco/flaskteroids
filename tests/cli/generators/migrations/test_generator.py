import pytest
from flaskteroids.cli.generators.migrations import generator


@pytest.fixture
def command(mocker):
    return mocker.patch.object(generator, 'command')


def test_generator(app, command):
    generator.migration('CreateUsersTable', ['name:str'])
    command.revision.assert_called()
