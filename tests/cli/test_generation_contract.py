import shutil
import tomllib
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest
from click.testing import CliRunner

from flaskteroids.cli.flaskteroids import cli


@pytest.mark.parametrize("name", ["my_app", "my-app", "My.App"])
def test_destination_basename_is_project_name(tmp_path, name):
    root = tmp_path / "parent with spaces" / name
    result = CliRunner().invoke(cli, ["new", str(root), "--skip-install"])
    assert result.exit_code == 0, result.output
    metadata = tomllib.loads((root / "pyproject.toml").read_text())
    assert metadata["project"]["name"] == name
    assert metadata["tool"]["uv"]["package"] is False
    assert not (root / "uv.lock").exists()
    assert not (root / ".venv").exists()
    assert not (root / "storage/development.sqlite3").exists()
    for resource in ("alembic.ini", "env.py", "script.py.mako", "versions/.keep"):
        assert (root / "db/migrate" / resource).is_file()


@pytest.mark.parametrize("name", ["bad name", "_bad", "bad!", "bad-"])
def test_invalid_basename_rejected_before_writing(tmp_path, name):
    root = tmp_path / name
    result = CliRunner().invoke(cli, ["new", str(root), "--skip-install"])
    assert result.exit_code == 2
    assert "APP_NAME" in result.output
    assert not root.exists()


def test_unavailable_version_rejected_before_writing(tmp_path, mocker):
    mocker.patch(
        "flaskteroids.cli.flaskteroids.version",
        side_effect=PackageNotFoundError("flaskteroids"),
    )
    root = tmp_path / "weblog"
    result = CliRunner().invoke(cli, ["new", str(root), "--skip-install"])
    assert result.exit_code == 1
    assert "version" in result.output
    assert not root.exists()


@pytest.mark.parametrize(
    ("version", "constraint"),
    [
        ("0.4.0", ">=0.4.0"),
        ("0.4.9", ">=0.4.9"),
        ("0.5.0", ">=0.5.0"),
        ("1.2.3", ">=1.2.3"),
        ("0.5.0rc1", "==0.5.0rc1"),
        ("0.5.0.dev1", "==0.5.0.dev1"),
        ("0.4.1+candidate", "==0.4.1+candidate"),
        ("1!0.4.1", ">=1!0.4.1"),
    ],
)
def test_new_pins_installed_generator_version_constraint(
    tmp_path, mocker, version, constraint
):
    mocker.patch("flaskteroids.cli.flaskteroids.version", return_value=version)
    root = tmp_path / "weblog"
    result = CliRunner().invoke(cli, ["new", str(root), "--skip-install"])
    assert result.exit_code == 0, result.output
    metadata = tomllib.loads((root / "pyproject.toml").read_text())
    assert metadata["project"]["dependencies"] == [
        f"flaskteroids{constraint}",
        "gunicorn",
    ]


def test_invalid_version_rejected_before_writing(tmp_path, mocker):
    mocker.patch("flaskteroids.cli.flaskteroids.version", return_value="unknown")
    root = tmp_path / "weblog"
    result = CliRunner().invoke(cli, ["new", str(root), "--skip-install"])
    assert result.exit_code == 1
    assert "version" in result.output
    assert not root.exists()


def test_missing_git_has_actionable_error(tmp_path, monkeypatch):
    tools = tmp_path / "tools"
    tools.mkdir()
    monkeypatch.setenv("PATH", str(tools))
    result = CliRunner().invoke(
        cli, ["new", str(tmp_path / "weblog"), "--skip-install"]
    )
    assert result.exit_code == 1
    assert "git" in result.output.casefold()


def test_skip_install_generates_application_with_uv_unavailable(tmp_path, monkeypatch):
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "git").symlink_to(shutil.which("git"))
    monkeypatch.setenv("PATH", str(tools))
    result = CliRunner().invoke(
        cli, ["new", str(tmp_path / "weblog"), "--skip-install"]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "weblog/pyproject.toml").is_file()


def test_default_new_without_uv_reports_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    root = tmp_path / "weblog"
    result = CliRunner().invoke(cli, ["new", str(root)])
    assert result.exit_code == 1
    assert "uv" in result.output.casefold()
    assert "bin/setup" in result.output
    assert not (root / "uv.lock").exists()


def test_new_reports_required_script_chmod_failure(tmp_path, mocker):
    mocker.patch.object(Path, "chmod", side_effect=PermissionError("read only"))
    result = CliRunner().invoke(
        cli, ["new", str(tmp_path / "weblog"), "--skip-install"]
    )
    assert result.exit_code == 1
    assert "bin/flask" in result.output
    assert "read only" in result.output


def test_default_new_propagates_install_failure(tmp_path, monkeypatch):
    tools = tmp_path / "tools"
    tools.mkdir()
    uv = tools / "uv"
    uv.write_text("#!/bin/bash\necho 'sync refused' >&2\nexit 37\n")
    uv.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tools}:/usr/bin:/bin")
    result = CliRunner().invoke(cli, ["new", str(tmp_path / "weblog")])
    assert result.exit_code == 1
    assert "sync refused" in result.output
    assert "37" in result.output
