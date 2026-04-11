import pytest
from flaskteroids.cli.generators.model.generator import generate


@pytest.fixture
def artifacts_builder(mocker):
    mock_builder = mocker.patch('flaskteroids.cli.generators.model.generator.ArtifactsBuilder')
    mock_ab = mocker.Mock()
    mock_builder.return_value = mock_ab
    return mock_ab


@pytest.fixture
def migrations_generate(mocker):
    return mocker.patch('flaskteroids.cli.generators.model.generator.migrations.generate')


class TestModelGenerator:

    @pytest.mark.usefixtures('artifacts_builder')
    def test_generate_calls_migrations_generate(self, migrations_generate):
        generate('User', [])
        migrations_generate.assert_called_once_with('CreateUsers', [])

    @pytest.mark.usefixtures('migrations_generate')
    def test_generate_creates_model_file(self, artifacts_builder):
        generate('User', [])
        expected_content = """
from app.models.application_model import ApplicationModel


class User(ApplicationModel):
    pass
    """
        artifacts_builder.file.assert_called_once_with(
            'app/models/user.py',
            expected_content
        )

    def test_generate_with_different_model_name(self, artifacts_builder, migrations_generate):
        generate('Post', [])
        migrations_generate.assert_called_once_with('CreatePosts', [])
        expected_content = """
from app.models.application_model import ApplicationModel


class Post(ApplicationModel):
    pass
    """
        artifacts_builder.file.assert_called_once_with(
            'app/models/post.py',
            expected_content
        )
