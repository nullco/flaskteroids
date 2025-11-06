import pytest
from unittest.mock import Mock, call, ANY
from flaskteroids.cli.generators.authentication.generator import generate


@pytest.fixture
def migrations(mocker):
    return mocker.patch('flaskteroids.cli.generators.authentication.generator.migrations')


@pytest.fixture
def artifacts_builder(mocker):
    ab = mocker.patch('flaskteroids.cli.generators.authentication.generator.ArtifactsBuilder')
    instance = Mock()
    ab.return_value = instance
    return instance


@pytest.fixture
def template(mocker):
    t = mocker.patch('flaskteroids.cli.generators.authentication.generator.template')
    t.return_value = "template_content"
    return t


class TestAuthenticationGenerator:

    @pytest.mark.usefixtures('migrations', 'template')
    def test_generate_adds_model_files(self, artifacts_builder):
        generate()
        artifacts_builder.file.assert_has_calls([
            call.file('app/models/session.py', 'template_content'),
            call.file('app/models/user.py', 'template_content'),
        ], any_order=False)

    @pytest.mark.usefixtures('migrations', 'template')
    def test_generate_adds_view_files(self, artifacts_builder):
        generate()
        artifacts_builder.file.assert_has_calls(
            [
                call.file('app/views/sessions/new.html', 'template_content'),
                call.file('app/views/passwords/new.html', 'template_content'),
                call.file('app/views/passwords/edit.html', 'template_content'),
                call.file('app/views/passwords_mailer/reset.html', 'template_content'),
                call.file('app/views/passwords_mailer/reset.txt', 'template_content'),
            ],
            any_order=False
        )

    @pytest.mark.usefixtures('migrations', 'template')
    def test_generate_adds_controller_files(self, artifacts_builder):
        generate()
        artifacts_builder.file.assert_has_calls([
            call.file('app/controllers/concerns/authentication.py', 'template_content'),
            call.file('app/controllers/sessions_controller.py', 'template_content'),
            call.file('app/controllers/passwords_controller.py', 'template_content'),
        ], any_order=False)

    @pytest.mark.usefixtures('migrations', 'template')
    def test_generate_adds_mailer_file(self, artifacts_builder):
        generate()
        artifacts_builder.file.assert_any_call('app/mailers/passwords_mailer.py', 'template_content')

    @pytest.mark.usefixtures('migrations', 'template')
    def test_generate_modifies_application_controller(self, artifacts_builder):
        generate()
        artifacts_builder.modify_py_file.assert_has_calls([
            call.modify_py_file('app/controllers/application_controller.py', ANY),
            call.modify_py_file('app/controllers/application_controller.py', ANY),
        ])

    @pytest.mark.usefixtures('migrations', 'template')
    def test_generate_modifies_routes(self, artifacts_builder):
        generate()
        artifacts_builder.modify_py_file.assert_any_call('config/routes.py', ANY)

    @pytest.mark.usefixtures('artifacts_builder', 'template')
    def test_generate_creates_migrations(self, migrations):
        generate()
        migrations.generate.assert_has_calls([
            call.generate('CreateUsersTable', ['email_address:str!', 'password_digest:str!']),
            call.generate('CreateSessionsTable', ['user:references', 'ip_address:str', 'user_agent:str']),
        ])
