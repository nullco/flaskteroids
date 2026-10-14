import subprocess
import sys

import pytest

from flaskteroids.cli.artifacts import ArtifactsBuilder, ArtifactsBuilderException


@pytest.fixture
def builder(tmp_path, mocker):
    notify = mocker.Mock()
    return ArtifactsBuilder(str(tmp_path), notify), notify


@pytest.mark.parametrize("method", ["run", "python_run"])
def test_prepared_argv_options_return_and_notification(
    builder, tmp_path, mocker, method
):
    instance, notify = builder
    run = mocker.patch(
        "subprocess.run", return_value=subprocess.CompletedProcess([], 0)
    )
    command = "tool --title 'two words'"
    assert getattr(instance, method)(command) is None
    argv = ["tool", "--title", "'two", "words'"]
    if method == "python_run":
        argv = [sys.executable, "-m", *argv]
    run.assert_called_once_with(
        argv, cwd=str(tmp_path), capture_output=True, text=True, check=False
    )
    notify.assert_called_once_with(f"    run  {command}")


@pytest.mark.parametrize("method", ["run", "python_run"])
@pytest.mark.parametrize("status", [1, 17, -9])
def test_command_failure_diagnostics_and_no_notification(
    builder, mocker, method, status
):
    instance, notify = builder
    mocker.patch(
        "subprocess.run",
        return_value=subprocess.CompletedProcess(
            [], status, stdout="out", stderr="problem"
        ),
    )
    with pytest.raises(ArtifactsBuilderException) as raised:
        getattr(instance, method)("tool argument")
    assert str(raised.value) == f"command tool argument returned {status}:\nproblem"
    notify.assert_not_called()


@pytest.mark.parametrize("method", ["run", "python_run"])
def test_launch_exception_is_unchanged(builder, mocker, method):
    instance, notify = builder
    error = FileNotFoundError("cannot launch")
    mocker.patch("subprocess.run", side_effect=error)
    with pytest.raises(FileNotFoundError) as raised:
        getattr(instance, method)("tool")
    assert raised.value is error
    notify.assert_not_called()


@pytest.mark.parametrize("method", ["run", "python_run"])
def test_real_command_working_directory_and_success(builder, tmp_path, capsys, method):
    instance, notify = builder
    (tmp_path / "proof.py").write_text(
        "from pathlib import Path\n"
        "Path('cwd.txt').write_text(str(Path.cwd()))\n"
        "print('captured output')\n"
    )
    command = f"{sys.executable} proof.py" if method == "run" else "proof"
    assert getattr(instance, method)(command) is None
    assert (tmp_path / "cwd.txt").read_text() == str(tmp_path)
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
    notify.assert_called_once_with(f"    run  {command}")


@pytest.mark.parametrize("method", ["run", "python_run"])
def test_real_command_stderr_and_failure(builder, tmp_path, method):
    instance, notify = builder
    (tmp_path / "proof.py").write_text(
        "import sys\nsys.stderr.write('real problem')\nsys.exit(3)\n"
    )
    command = f"{sys.executable} proof.py" if method == "run" else "proof"
    with pytest.raises(ArtifactsBuilderException) as raised:
        getattr(instance, method)(command)
    assert str(raised.value) == f"command {command} returned 3:\nreal problem"
    notify.assert_not_called()
