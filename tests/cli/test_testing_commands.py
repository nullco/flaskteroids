import os
from importlib.metadata import requires

import pytest
from click.testing import CliRunner
from flask.cli import FlaskGroup
from packaging.requirements import Requirement


@pytest.mark.parametrize("dependency", ["pytest", "pytest-xdist", "playwright"])
def test_testing_dependencies_are_core_requirements(dependency):
    requirements = [Requirement(value) for value in requires("flaskteroids")]

    assert any(
        requirement.name == dependency and requirement.marker is None
        for requirement in requirements
    )


@pytest.fixture
def flask_cli(mocker):
    create_app = mocker.Mock(side_effect=AssertionError("Application loaded too early"))
    return FlaskGroup(create_app=create_app)


@pytest.mark.parametrize(
    ("command", "marker"),
    [("test", "not system"), ("test:system", "system")],
)
def test_flask_commands_run_pytest_without_loading_application(
    flask_cli, mocker, monkeypatch, command, marker
):
    monkeypatch.setenv("FLASKTEROIDS_ENV", "production")

    def run_pytest(args):
        assert os.environ["FLASKTEROIDS_ENV"] == "test"
        return 0

    pytest_main = mocker.patch("pytest.main", side_effect=run_pytest)

    result = CliRunner().invoke(flask_cli, [command, "-q", "-n", "auto", "test/models"])

    assert result.exit_code == 0, result.output
    pytest_main.assert_called_once_with(
        ["-m", marker, "-q", "-n", "auto", "test/models"]
    )
    assert os.environ["FLASKTEROIDS_ENV"] == "production"


@pytest.mark.parametrize("command", ["test", "test:system"])
@pytest.mark.parametrize("exit_code", [0, 1, 2, 3, 4, 5])
def test_test_command_preserves_exit_code_and_restores_unset_environment(
    cli_runner, mocker, monkeypatch, exit_code, command
):
    mocker.patch("pytest.main", return_value=exit_code)
    monkeypatch.delenv("FLASKTEROIDS_ENV", raising=False)

    result = cli_runner.invoke(args=[command, "-q"])

    assert result.exit_code == (0 if exit_code == 5 else exit_code)
    assert ("No tests collected" in result.output) is (exit_code == 5)
    assert "FLASKTEROIDS_ENV" not in os.environ


def test_test_command_restores_environment_on_error(cli_runner, mocker, monkeypatch):
    mocker.patch("pytest.main", side_effect=RuntimeError("pytest failed"))
    monkeypatch.setenv("FLASKTEROIDS_ENV", "development")

    result = cli_runner.invoke(args=["test"])

    assert result.exit_code == 1
    assert isinstance(result.exception, RuntimeError)
    assert os.environ["FLASKTEROIDS_ENV"] == "development"
