from pathlib import Path

import pytest
from click.testing import CliRunner

from flaskteroids.cli.flaskteroids import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_agent_skills_path(runner, monkeypatch, tmp_path, mocker):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FLASK_APP", "wsgi:app")
    (tmp_path / "wsgi.py").write_text("raise RuntimeError('Application cannot boot')\n")
    initialize = mocker.patch("flaskteroids.Application.initialize")

    result = runner.invoke(cli, ["agent-skills", "path"])

    assert result.exit_code == 0
    skills_path = Path(result.output.strip())
    assert result.output == f"{skills_path}\n"
    assert skills_path.is_absolute()
    assert skills_path.is_dir()
    assert skills_path.parts[-2:] == (".agents", "skills")
    skill = skills_path / "using-flaskteroids" / "SKILL.md"
    assert "name: using-flaskteroids" in skill.read_text()
    initialize.assert_not_called()


@pytest.mark.parametrize(
    "args", [["agent-skills", "--help"], ["agent-skills", "path", "--help"]]
)
def test_agent_skills_help(runner, args):
    result = runner.invoke(cli, args)

    assert result.exit_code == 0
    assert "path" in result.output
