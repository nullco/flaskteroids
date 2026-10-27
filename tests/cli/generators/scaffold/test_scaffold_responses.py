import os
import shutil
import subprocess
import sys
from pathlib import Path

from flaskteroids.cli.flaskteroids import cli
from tests.assertions import assert_pytest_passed


def test_generated_scaffold_serves_json_and_html_responses(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cli.main(args=["new", "weblog", "--skip-install"], standalone_mode=False)
    root = tmp_path / "weblog"
    environment = os.environ | {
        "PYTHONPATH": str(Path(__file__).parents[4]),
        "FLASKTEROIDS_ENV": "test",
    }

    def run(*args):
        result = subprocess.run(
            [sys.executable, "-m", "flask", *args],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result

    run(
        "generate",
        "scaffold",
        "Post",
        "title:string",
        "completed:boolean",
        "settings:json",
    )
    source = Path(__file__).parents[2] / "fixtures/scaffold"
    shutil.copyfile(source / "post.py", root / "app/models/post.py")
    shutil.copyfile(
        source / "responses.py", root / "test/controllers/responses_test.py"
    )

    report = root / "controller-tests.xml"
    run("test", "-q", "--junitxml", str(report), "test/controllers")

    assert_pytest_passed(report)
