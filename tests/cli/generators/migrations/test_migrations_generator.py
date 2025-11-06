import pytest
from flaskteroids.cli.generators.migrations import generator


@pytest.fixture
def command(mocker):
    return mocker.patch.object(generator, 'command')


@pytest.mark.usefixtures('app_ctx')
def test_generator(command):
    generator.generate('CreateUsersTable', ['name:str'])
    command.revision.assert_called()
