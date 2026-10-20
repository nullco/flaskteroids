import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from flaskteroids.cli.flaskteroids import cli


@pytest.fixture(scope="module")
def generated_app_factory(tmp_path_factory):
    def create(name):
        root = tmp_path_factory.mktemp("application") / name
        result = CliRunner().invoke(cli, ["new", str(root), "--skip-install"])
        assert result.exit_code == 0, result.output
        (root / ".venv").symlink_to(Path(sys.prefix), target_is_directory=True)
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("FLASK", "UV_"))
        }
        environment.update(
            FLASK_ENV="test",
            PYTHONPATH=os.pathsep.join((str(root), str(Path(__file__).parents[1]))),
            DATABASE_URL=os.environ.get(
                "DATABASE_URL", "sqlite:///storage/test.sqlite3"
            ),
        )

        def run(*args, script=None):
            command = (
                [
                    sys.executable,
                    str(Path(__file__).parent / "integration/scenarios" / script),
                    *args,
                ]
                if script is not None
                else [str(root / "bin/flask"), *args]
            )
            result = subprocess.run(
                command,
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            return result

        return root, run

    return create


@pytest.fixture(scope="module")
def generated_store(generated_app_factory):
    root, run = generated_app_factory("store")
    run("db:create")
    run("generate", "scaffold", "Product", "name:string", "quantity:integer")
    run("generate", "model", "Subscriber", "product:references", "email:string")
    run("generate", "authentication")
    source = Path(__file__).parent / "integration/application/store"
    for path in source.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            destination = root / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
    run("db:prepare")
    migrations = list((root / "db/migrate/versions").glob("*.py"))
    try:
        yield root, run
    finally:
        for _ in migrations:
            run("db:rollback")
