import base64
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner
from flask.cli import cli

pytestmark = pytest.mark.generated_app

FRAMEWORK_ROOT = Path(__file__).parents[2]


@pytest.fixture
def generated_assets_app(tmp_path):
    root = tmp_path / "parent with spaces" / "weblog"
    result = CliRunner().invoke(cli, ["new", str(root), "--skip-install"])
    assert result.exit_code == 0, result.output
    (root / ".venv").symlink_to(sys.prefix, target_is_directory=True)
    (root / "app/assets/stylesheets/application.css").write_text(
        'body { color: rgb(255, 0, 0); background-image: url("../images/logo.png"); min-height: 20px; }'
    )
    (root / "app/assets/images/logo.png").write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aK1sAAAAASUVORK5CYII="
        )
    )
    fixtures = Path(__file__).parent / "fixtures/assets"
    shutil.copytree(fixtures / "modules", root / "app/javascript", dirs_exist_ok=True)
    shutil.copyfile(fixtures / "optional.js", root / "vendor/javascript/optional.js")
    shutil.copyfile(fixtures / "importmap.py", root / "config/importmap.py")
    return root


def run(root, *args, environment="development"):
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("FLASK", "DATABASE", "SECRET_KEY"))
    }
    env |= {
        "PYTHONPATH": os.pathsep.join((str(root), str(FRAMEWORK_ROOT))),
        "FLASKTEROIDS_ENV": environment,
        "FLASKTEROIDS_DATABASE_URL": "sqlite:///:memory:",
    }
    return subprocess.run(
        args, cwd=root.parent, env=env, capture_output=True, text=True, check=False
    )


@pytest.mark.parametrize("launcher", ["bin/flask", "flask"])
def test_precompilation_runs_without_application_boot_or_runtime_secrets(
    generated_assets_app, launcher
):
    root = generated_assets_app
    (root / "config/application.py").write_text(
        'raise AssertionError("application booted")'
    )
    (root / "config/master.key").unlink()
    (root / "config/initializers/fail.py").write_text(
        'raise AssertionError("initializer ran")'
    )
    command = (
        [str(root / launcher), "assets:precompile"]
        if launcher == "bin/flask"
        else [sys.executable, "-m", "flask", "assets:precompile", "--root", str(root)]
    )
    result = run(root, *command, environment="production")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (root / "public/assets/.manifest.json").is_file()
    assert not list((root / "storage").glob("*.sqlite3"))


@pytest.mark.parametrize("environment", ["development", "production"])
def test_generated_layout_loads_stylesheet_from_outside_app_root(
    generated_assets_app, environment
):
    root = generated_assets_app
    if environment == "production":
        result = run(
            root, str(root / "bin/flask"), "assets:precompile", environment=environment
        )
        assert result.returncode == 0, result.stdout + result.stderr
    result = run(
        root,
        sys.executable,
        str(Path(__file__).parent / "fixtures/assets/layout.py"),
        environment,
        environment=environment,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_generated_docker_installs_runtime_and_precompiles_before_runtime_user(
    generated_assets_app,
):
    root = generated_assets_app
    dockerfile = (root / "Dockerfile").read_text()
    assert "uv sync --locked --no-dev --no-install-project" in dockerfile
    assert "COPY --from=deps /app/.venv /app/.venv" in dockerfile
    assert "pip" not in dockerfile
    assert 'CMD ["gunicorn", "wsgi:app"' in dockerfile
    assert dockerfile.index("COPY . .") < dockerfile.index(
        "RUN bin/flask assets:precompile"
    )
    assert dockerfile.index("RUN bin/flask assets:precompile") < dockerfile.index(
        "USER app"
    )
    for name in (".gitignore", ".dockerignore"):
        assert "public/assets/" in (root / name).read_text()


@pytest.mark.system
@pytest.mark.parametrize("environment", ["development", "production"])
def test_generated_stylesheet_loads_in_browser(generated_assets_app, environment):
    if environment == "production":
        compiled = run(
            generated_assets_app,
            str(generated_assets_app / "bin/flask"),
            "assets:precompile",
            environment=environment,
        )
        assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    result = run(
        generated_assets_app,
        sys.executable,
        str(Path(__file__).parent / "fixtures/assets/browser.py"),
        environment,
        environment=environment,
    )
    assert result.returncode == 0, result.stdout + result.stderr
