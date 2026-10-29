import pytest
import yaml
from flask.cli import cli

from flaskteroids.cli.artifacts import ArtifactsBuilder, ArtifactsBuilderException


@pytest.fixture
def artifacts_builder(mocker):
    mocker.patch("flaskteroids.cli.new.initialize_migrations")
    mock_builder = mocker.patch("flaskteroids.cli.new.ArtifactsBuilder")
    mock_ab = mocker.Mock()
    mock_builder.return_value = mock_ab
    return mock_ab


def test_new_creates_application_and_runs_setup(cli_runner, artifacts_builder):
    result = cli_runner.invoke(cli, ["new", "test_app"])
    assert result.exit_code == 0
    artifacts_builder.dir.assert_called()
    artifacts_builder.run.assert_any_call("bin/setup")
    assert any(
        args[0] == "pyproject.toml" and "flaskteroids" in args[1]
        for args, _ in artifacts_builder.file.call_args_list
    )
    created_files = {args[0] for args, _ in artifacts_builder.file.call_args_list}
    assert {
        "config/importmap.py",
        "app/javascript/application.js",
        "bin/importmap",
        "vendor/javascript/.keep",
        "config/application.py",
        "config/environment.py",
        "config/environments/development.py",
        "config/environments/test.py",
        "config/environments/production.py",
        "config/database.yml",
        "config/locales/en.yml",
        "config/credentials.yml.enc",
        "config/master.key",
        "test/__init__.py",
        "test/conftest.py",
        "test/test_helper.py",
        ".github/workflows/test.yml",
        ".agents/skills/using-flaskteroids/SKILL.md",
    }.issubset(created_files)


def test_new_generates_agent_skill_loader(cli_runner, tmp_path, mocker):
    mocker.patch.object(ArtifactsBuilder, "python_run")
    mocker.patch.object(ArtifactsBuilder, "run")
    app_path = tmp_path / "test_app"

    result = cli_runner.invoke(cli, ["new", str(app_path), "--skip-install"])

    assert result.exit_code == 0
    skill_path = app_path / ".agents" / "skills" / "using-flaskteroids" / "SKILL.md"
    text = skill_path.read_text()
    _, frontmatter, body = text.split("---", 2)
    metadata = yaml.safe_load(frontmatter)
    assert metadata["name"] == "using-flaskteroids"
    assert metadata["description"]
    assert "flask agent-skills path" in body
    assert "using-flaskteroids/SKILL.md" in body


def test_new_reports_artifact_creation_errors(cli_runner, artifacts_builder):
    artifacts_builder.dir.side_effect = ArtifactsBuilderException("Test error")
    result = cli_runner.invoke(cli, ["new", "test_app"])
    assert result.exit_code == 1
    assert "Test error" in result.output
