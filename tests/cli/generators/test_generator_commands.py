import pytest
from flaskteroids.cli.generators.commands import generate


@pytest.fixture
def migrations_generate(mocker):
    return mocker.patch('flaskteroids.cli.generators.commands.migrations.generate')


@pytest.fixture
def model_generate(mocker):
    return mocker.patch('flaskteroids.cli.generators.commands.model.generate')


@pytest.fixture
def controller_generate(mocker):
    return mocker.patch('flaskteroids.cli.generators.commands.controller.generate')


@pytest.fixture
def mailer_generate(mocker):
    return mocker.patch('flaskteroids.cli.generators.commands.mailer.generate')


@pytest.fixture
def scaffold_generate(mocker):
    return mocker.patch('flaskteroids.cli.generators.commands.scaffold.generate')


@pytest.fixture
def resource_generate(mocker):
    return mocker.patch('flaskteroids.cli.generators.commands.resource.generate')


@pytest.fixture
def authentication_generate(mocker):
    return mocker.patch('flaskteroids.cli.generators.commands.authentication.generate')


class TestGenerateCommands:

    def test_generate_group_exists(self):
        assert generate.name == 'generate'

    def test_generate_migration_command(self, cli_runner, migrations_generate):
        result = cli_runner.invoke(generate, ['migration', 'CreateUsers', 'name:string', 'email:string'])
        assert result.exit_code == 0
        migrations_generate.assert_called_once_with('CreateUsers', ['name:string', 'email:string'])

    def test_generate_model_command(self, cli_runner, model_generate):
        result = cli_runner.invoke(generate, ['model', 'User', 'name:string'])
        assert result.exit_code == 0
        model_generate.assert_called_once_with('User', ['name:string'])

    def test_generate_controller_command(self, cli_runner, controller_generate):
        result = cli_runner.invoke(generate, ['controller', 'UsersController', 'index', 'show'])
        assert result.exit_code == 0
        controller_generate.assert_called_once_with('UsersController', ('index', 'show'), False)

    def test_generate_controller_with_skip_routes(self, cli_runner, controller_generate):
        result = cli_runner.invoke(generate, ['controller', 'UsersController', 'index', '--skip-routes'])
        assert result.exit_code == 0
        controller_generate.assert_called_once_with('UsersController', ('index',), True)

    def test_generate_mailer_command(self, cli_runner, mailer_generate):
        result = cli_runner.invoke(generate, ['mailer', 'UserMailer', 'welcome', 'confirmation'])
        assert result.exit_code == 0
        mailer_generate.assert_called_once_with('UserMailer', ('welcome', 'confirmation'))

    def test_generate_scaffold_command(self, cli_runner, scaffold_generate):
        result = cli_runner.invoke(generate, ['scaffold', 'User', 'name:string', 'email:string'])
        assert result.exit_code == 0
        scaffold_generate.assert_called_once_with('User', ['name:string', 'email:string'])

    def test_generate_resource_command(self, cli_runner, resource_generate):
        result = cli_runner.invoke(generate, ['resource', 'User', 'name:string'])
        assert result.exit_code == 0
        resource_generate.assert_called_once_with('User', ['name:string'])

    def test_generate_authentication_command(self, cli_runner, authentication_generate):
        result = cli_runner.invoke(generate, ['authentication'])
        assert result.exit_code == 0
        authentication_generate.assert_called_once_with()

    def test_generate_help(self, cli_runner):
        result = cli_runner.invoke(generate, ['--help'])
        assert result.exit_code == 0
        assert 'migration' in result.output
        assert 'model' in result.output
        assert 'controller' in result.output
        assert 'mailer' in result.output
        assert 'scaffold' in result.output
        assert 'resource' in result.output
        assert 'authentication' in result.output
