import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from flaskteroids.cli.flaskteroids import cli


@pytest.fixture
def scripts_app(tmp_path):
    root = tmp_path / "parent with spaces" / "weblog"
    result = CliRunner().invoke(cli, ["new", str(root), "--skip-install"])
    assert result.exit_code == 0, result.output
    return root


@pytest.fixture
def script_environment(scripts_app, tmp_path):
    tools = tmp_path / "tools"
    tools.mkdir()
    uv = tools / "uv"
    uv.write_text(
        '#!/bin/bash\nprintf "uv:%s\\n" "$*" >> "$TRACE"\nexit "${SYNC_STATUS:-0}"\n'
    )
    uv.chmod(0o755)
    python = scripts_app / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text(
        "#!/bin/bash\n"
        'printf "%s\\n" "$PWD" "${FLASKTEROIDS_ENV-unset}" "${FLASKTEROIDS_DATABASE_URL-unset}" "$@" >> "$TRACE"\n'
        'exit "${PREPARE_STATUS:-0}"\n'
    )
    python.chmod(0o755)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("FLASK", "DATABASE", "UV_"))
    }
    return env | {"PATH": f"{tools}:/usr/bin:/bin", "TRACE": str(tmp_path / "trace")}


def run_script(root, name, environment, *args):
    return subprocess.run(
        [str(root / "bin" / name), *args],
        cwd=root.parent,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


@pytest.mark.parametrize(("name", "args"), [("flask", ["--help"]), ("jobs", ["start"])])
def test_launcher_missing_environment_is_actionable(scripts_app, name, args):
    result = run_script(scripts_app, name, os.environ, *args)
    assert result.returncode != 0
    assert "bin/setup" in result.stderr


@pytest.mark.parametrize(
    ("name", "args", "forwarded"),
    [
        (
            "flask",
            ["test", "-k", "title with spaces", ""],
            ["-m", "flask", "test", "-k", "title with spaces", ""],
        ),
        (
            "jobs",
            ["start"],
            ["-m", "celery", "-A", "jobs", "worker", "--loglevel=info"],
        ),
        (
            "jobs",
            ["start", "--hostname", "worker with spaces", "--loglevel=debug", ""],
            [
                "-m",
                "celery",
                "-A",
                "jobs",
                "worker",
                "--loglevel=info",
                "--hostname",
                "worker with spaces",
                "--loglevel=debug",
                "",
            ],
        ),
    ],
)
def test_launcher_preserves_root_arguments_environment_and_status(
    scripts_app, script_environment, name, args, forwarded
):
    env = script_environment | {
        "FLASKTEROIDS_ENV": "production",
        "FLASKTEROIDS_DATABASE_URL": "sqlite:///other.sqlite3",
        "PREPARE_STATUS": "23",
    }
    result = run_script(scripts_app, name, env, *args)
    assert result.returncode == 23
    assert Path(env["TRACE"]).read_text().splitlines() == [
        str(scripts_app),
        "production",
        "sqlite:///other.sqlite3",
        *forwarded,
    ]


@pytest.mark.parametrize("args", [[], ["stop"], ["--concurrency=2"]])
def test_jobs_launcher_rejects_missing_or_unknown_commands(
    scripts_app, script_environment, args
):
    result = run_script(scripts_app, "jobs", script_environment, *args)
    assert result.returncode != 0
    assert "Usage:" in result.stderr
    assert not Path(script_environment["TRACE"]).exists()


def test_jobs_launcher_loads_generated_celery_application(scripts_app):
    (scripts_app / ".venv").symlink_to(sys.prefix, target_is_directory=True)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("FLASK", "DATABASE", "CELERY"))
    }
    env["FLASKTEROIDS_ENV"] = "development"
    env["PYTHONPATH"] = os.pathsep.join(
        (str(scripts_app), str(Path(__file__).parents[2]))
    )
    result = run_script(scripts_app, "jobs", env, "start", "--help")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--concurrency" in result.stdout


@pytest.mark.parametrize("environment", [None, "test", "production"])
def test_setup_syncs_then_prepares_selected_database(
    scripts_app, script_environment, environment
):
    env = script_environment | {
        "FLASKTEROIDS_DATABASE_URL": "sqlite:///selected.sqlite3"
    }
    if environment is not None:
        env["FLASKTEROIDS_ENV"] = environment
    result = run_script(scripts_app, "setup", env)
    assert result.returncode == 0, result.stderr
    assert Path(env["TRACE"]).read_text().splitlines() == [
        "uv:sync",
        str(scripts_app),
        environment or "development",
        "sqlite:///selected.sqlite3",
        "-m",
        "flask",
        "db:prepare",
    ]


@pytest.mark.parametrize(
    ("failure", "status", "prepared"),
    [("SYNC_STATUS", "17", False), ("PREPARE_STATUS", "19", True)],
)
def test_setup_stops_remaining_steps_on_failure(
    scripts_app, script_environment, failure, status, prepared
):
    env = script_environment | {failure: status}
    result = run_script(scripts_app, "setup", env)
    assert result.returncode == int(status)
    assert ("db:prepare" in Path(env["TRACE"]).read_text()) is prepared


def test_asset_launcher_uses_bootless_cli(scripts_app, script_environment):
    result = run_script(scripts_app, "flask", script_environment, "assets:precompile")
    assert result.returncode == 0, result.stderr
    trace = Path(script_environment["TRACE"]).read_text().splitlines()
    assert trace[-3:] == ["-m", "flaskteroids", "assets:precompile"]


def test_setup_reports_missing_uv_before_installation(scripts_app, script_environment):
    env = script_environment | {"PATH": "/usr/bin:/bin"}
    result = run_script(scripts_app, "setup", env)
    assert result.returncode != 0
    assert "uv" in result.stderr.casefold()
    assert not Path(env["TRACE"]).exists()


@pytest.mark.parametrize(
    ("args", "prepares"),
    [
        (["gunicorn", "wsgi:app", "--workers", "2"], True),
        (["gunicorn", "other:app"], False),
        (["celery", "-A", "jobs", "worker"], False),
        (["bash", "-c", "echo bypass"], False),
    ],
)
def test_entrypoint_only_prepares_default_web_command(
    scripts_app, script_environment, args, prepares
):
    tools = Path(script_environment["PATH"].split(":")[0])
    for name in ("gunicorn", "celery"):
        command = tools / name
        command.write_text(
            '#!/bin/bash\nprintf "exec:%s\\n" "$*" >> "$TRACE"\nexit 29\n'
        )
        command.chmod(0o755)
    result = run_script(scripts_app, "docker-entrypoint", script_environment, *args)
    assert result.returncode == (0 if args[0] == "bash" else 29)
    trace = Path(script_environment["TRACE"])
    assert (trace.exists() and "db:prepare" in trace.read_text()) is prepares
    if args[0] != "bash":
        assert trace.read_text().splitlines()[-1] == "exec:" + " ".join(args[1:])


def test_entrypoint_starts_jobs_without_database_preparation(
    scripts_app, script_environment
):
    result = run_script(
        scripts_app, "docker-entrypoint", script_environment, "bin/jobs", "start"
    )
    assert result.returncode == 0, result.stderr
    trace = Path(script_environment["TRACE"]).read_text().splitlines()
    assert trace[-6:] == ["-m", "celery", "-A", "jobs", "worker", "--loglevel=info"]
    assert "db:prepare" not in trace


def test_entrypoint_stops_web_startup_on_preparation_failure(
    scripts_app, script_environment
):
    env = script_environment | {"PREPARE_STATUS": "31"}
    result = run_script(scripts_app, "docker-entrypoint", env, "gunicorn", "wsgi:app")
    assert result.returncode == 31
    assert "exec:" not in Path(env["TRACE"]).read_text()


def test_release_delegates_and_rejects_unknown_tasks(scripts_app, script_environment):
    result = run_script(scripts_app, "release", script_environment, "migrate")
    assert result.returncode == 0
    assert Path(script_environment["TRACE"]).read_text().endswith("db:prepare\n")
    for args in ([], ["assets:precompile"], ["migrate", "extra"]):
        result = run_script(scripts_app, "release", script_environment, *args)
        assert result.returncode != 0


@pytest.mark.parametrize("name", ["flask", "jobs", "docker-entrypoint"])
def test_launchers_replace_process_and_preserve_termination(
    scripts_app, script_environment, name
):
    (scripts_app / ".venv/bin/python").write_text("#!/bin/bash\nexec /bin/sleep 60\n")
    args = [str(scripts_app / "bin" / name)]
    if name == "jobs":
        args += ["start"]
    elif name == "docker-entrypoint":
        args += ["/bin/sleep", "60"]
    process = subprocess.Popen(args, env=script_environment, cwd=scripts_app.parent)
    try:
        # Wait for exec, not for a fixed amount of scheduling time.
        for _ in range(100):
            if Path(f"/proc/{process.pid}/comm").read_text().strip() == "sleep":
                break
            time.sleep(0.01)
        else:
            pytest.fail("launcher did not exec sleep")
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=5) == -signal.SIGTERM
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_scripts_use_valid_syntax_executable_modes_and_safe_defaults(scripts_app):
    for path in (scripts_app / "bin").iterdir():
        assert path.stat().st_mode & 0o111
        result = subprocess.run(
            ["bash", "-n", str(path)], capture_output=True, check=False
        )
        assert result.returncode == 0, result.stderr
        assert path.read_bytes().startswith(b"#!/usr/bin/env bash\n")
        assert path.read_bytes().endswith(b"\n")
    procfile = dict(
        line.split(": ", 1)
        for line in (scripts_app / "Procfile").read_text().splitlines()
    )
    assert procfile["worker"] == "bin/jobs start"
    assert not (scripts_app / "deploy/README.md").stat().st_mode & 0o111
    for path in ("kamal.yml", ".github/workflows/deploy.yml", "deploy/release.sh"):
        assert not (scripts_app / path).exists()
    assert "uv.lock" not in (scripts_app / ".gitignore").read_text()
