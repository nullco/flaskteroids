import pytest
from flaskteroids.cli.generators.mailer.generator import generate, _mailer, _html_view, _txt_view


@pytest.fixture
def cmd_parser(mocker):
    parser = mocker.patch('flaskteroids.cli.generators.mailer.generator.cmd_parser')
    parser.parse.return_value = {'parsed': {'snake': 'test_mailer', 'camel': 'TestMailer'}}
    return parser


@pytest.fixture
def artifacts_builder(mocker):
    mock_builder = mocker.patch('flaskteroids.cli.generators.mailer.generator.ArtifactsBuilder')
    mock_ab = mocker.Mock()
    mock_builder.return_value = mock_ab
    return mock_ab


class TestMailerGenerator:

    @pytest.mark.usefixtures('cmd_parser')
    def test_generate_creates_mailer_file(self, artifacts_builder, mocker):
        generate('test_mailer', ['welcome'])
        artifacts_builder.file.assert_any_call('app/mailers/test_mailer_mailer.py', mocker.ANY)

    @pytest.mark.usefixtures('cmd_parser')
    def test_generate_creates_views_directory(self, artifacts_builder):
        generate('test_mailer', ['welcome'])
        artifacts_builder.dir.assert_called_once_with('app/views/test_mailer_mailer/')

    @pytest.mark.usefixtures('cmd_parser')
    def test_generate_creates_view_files_for_actions(self, artifacts_builder, mocker):
        generate('test_mailer', ['welcome', 'goodbye'])
        expected_file_calls = [
            mocker.call('app/views/test_mailer_mailer/welcome.html', mocker.ANY),
            mocker.call('app/views/test_mailer_mailer/welcome.txt', mocker.ANY),
            mocker.call('app/views/test_mailer_mailer/goodbye.html', mocker.ANY),
            mocker.call('app/views/test_mailer_mailer/goodbye.txt', mocker.ANY),
        ]
        artifacts_builder.file.assert_has_calls(expected_file_calls, any_order=True)
