import pytest
from flaskteroids.cli.generators.resource.generator import generate


@pytest.fixture
def artifacts_builder(mocker):
    mock_builder = mocker.patch('flaskteroids.cli.generators.resource.generator.ArtifactsBuilder')
    mock_ab = mocker.Mock()
    mock_builder.return_value = mock_ab
    return mock_ab


@pytest.fixture
def model(mocker):
    return mocker.patch('flaskteroids.cli.generators.resource.generator.model')


@pytest.mark.usefixtures('app_ctx', 'artifacts_builder', 'model')
class TestResourceGenerator:

    def test_generate_creates_controller_file(self, artifacts_builder, mocker):
        generate('User', [])
        artifacts_builder.file.assert_called_once_with('app/controllers/users_controller.py', mocker.ANY)

    def test_generate_modifies_routes(self, artifacts_builder, mocker):
        generate('User', [])
        artifacts_builder.modify_py_file.assert_called_once_with('config/routes.py', mocker.ANY)

    def test_generate_calls_model_generate(self, model):
        generate('User', ['field:str'])
        model.generate.assert_called_once_with('User', ['field:str'])
