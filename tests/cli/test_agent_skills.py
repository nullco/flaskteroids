from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from flask.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_agent_skills_path_returns_installed_guidance_independently_of_application(
    runner, monkeypatch, tmp_path, mocker
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FLASK_APP", "wsgi:app")
    (tmp_path / "wsgi.py").write_text("raise RuntimeError('Application cannot boot')\n")
    initialize = mocker.patch("flaskteroids.Application.initialize")

    result = runner.invoke(cli, ["agent-skills", "path"])

    assert result.exit_code == 0
    skills_path = Path(result.output.strip())
    assert skills_path.is_absolute()
    skill = skills_path / "using-flaskteroids" / "SKILL.md"
    guidance = skill.read_text()
    _, frontmatter, body = guidance.split("---", 2)
    assert yaml.safe_load(frontmatter)["name"] == "using-flaskteroids"
    assert body.strip()
    initialize.assert_not_called()
