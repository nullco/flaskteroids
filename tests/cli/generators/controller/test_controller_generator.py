import pytest
from flaskteroids.cli.generators.controller.generator import generate


@pytest.fixture
def artifacts_builder(mocker):
    mock_builder = mocker.patch('flaskteroids.cli.generators.controller.generator.ArtifactsBuilder')
    mock_ab = mocker.Mock()
    mock_builder.return_value = mock_ab
    return mock_ab


class TestControllerGenerator:

    def test_generate_creates_controller_file(self, artifacts_builder, mocker):
        generate('TestController', ['index'])
        artifacts_builder.file.assert_any_call('app/controllers/test_controller_controller.py', mocker.ANY)

    def test_generate_creates_helper_file(self, artifacts_builder, mocker):
        generate('TestController', ['index'])
        artifacts_builder.file.assert_any_call('app/helpers/test_controller_helper.py', mocker.ANY)

    def test_generate_creates_views_directory(self, artifacts_builder):
        generate('TestController', ['index'])
        artifacts_builder.dir.assert_called_once_with('app/views/test_controller/')

    def test_generate_creates_view_files_for_actions(self, artifacts_builder, mocker):
        generate('TestController', ['index', 'show'])
        expected_file_calls = [
            mocker.call('app/views/test_controller/index.html', mocker.ANY),
            mocker.call('app/views/test_controller/show.html', mocker.ANY),
        ]
        artifacts_builder.file.assert_has_calls(expected_file_calls, any_order=True)

    def test_generate_adds_routes_when_not_skipped(self, artifacts_builder, mocker):
        generate('TestController', ['index'])
        artifacts_builder.modify_py_file.assert_called_once_with('config/routes.py', mocker.ANY)

    def test_generate_skips_routes_when_specified(self, artifacts_builder):
        generate('TestController', ['index'], skip_routes=True)
        artifacts_builder.modify_py_file.assert_not_called()
