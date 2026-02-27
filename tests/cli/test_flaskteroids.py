import pytest
from flaskteroids.cli.flaskteroids import cli
from flaskteroids.cli.artifacts import ArtifactsBuilderException


@pytest.fixture
def artifacts_builder(mocker):
    mock_builder = mocker.patch("flaskteroids.cli.flaskteroids.ArtifactsBuilder")
    mock_ab = mocker.Mock()
    mock_builder.return_value = mock_ab
    return mock_ab


def test_cli_is_click_group():
    assert cli.name == "cli"


def test_new_command(cli_runner, artifacts_builder):
    result = cli_runner.invoke(cli, ["new", "test_app"])
    assert result.exit_code == 0
    artifacts_builder.dir.assert_called()
    artifacts_builder.file.assert_called()
    artifacts_builder.python_run.assert_called_with("flask db:init")
    artifacts_builder.run.assert_called()
    # ensure a pyproject.toml is created and it contains flaskteroids as a dependency
    assert any(
        args[0] == "pyproject.toml" and "flaskteroids" in args[1]
        for args, _ in artifacts_builder.file.call_args_list
    )


def test_new_command_error(cli_runner, artifacts_builder):
    artifacts_builder.dir.side_effect = ArtifactsBuilderException("Test error")
    result = cli_runner.invoke(cli, ["new", "test_app"])
    assert result.exit_code == 0
    assert "Error creating new flaskteroids app: Test error" in result.output


def test_cli_help(cli_runner):
    result = cli_runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "new" in result.output
