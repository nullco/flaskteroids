"""Opt-in network acceptance: python scripts/accept_generated_app.py --wheel PATH.

Uses the supplied candidate before default installation, never checkout PYTHONPATH.
Browser installation is explicit via --browser; Docker acceptance is separate.
The disposable work directory is retained for diagnosis and further Docker checks.
"""

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    work = args.work_dir or Path(tempfile.mkdtemp(prefix="flaskteroids-acceptance-"))
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(
            (
                "FLASK",
                "DATABASE",
                "UV_",
                "PYTHON",
                "VIRTUAL_ENV",
                "SECRET_KEY",
                "CELERY",
                "ATTACHMENTS",
                "PLAYWRIGHT",
            )
        )
    }
    environment.update(UV_FIND_LINKS=str(wheel.parent), UV_PYTHON="3.14")

    def run(*command, cwd=work, env=None, success=True):
        print("+", " ".join(map(str, command)), flush=True)
        result = subprocess.run(
            list(map(str, command)),
            cwd=cwd,
            env=environment | (env or {}),
            text=True,
            capture_output=True,
            check=False,
        )
        print(result.stdout, end="")
        print(result.stderr, end="")
        if success and result.returncode:
            raise RuntimeError(f"Command failed ({result.returncode}): {command}")
        return result

    generator = work / "generator"
    run("uv", "venv", "--python", "3.14", generator)
    run("uv", "pip", "install", "--python", generator / "bin/python", wheel)
    command = generator / "bin/flaskteroids"
    parent = work / "parent with spaces"
    parent.mkdir()
    run(command, "new", "weblog", cwd=parent)
    root = parent / "weblog"
    assert (root / "uv.lock").is_file()
    assert (root / "storage/development.sqlite3").is_file()
    assert not (root / ".venv/bin/pip").exists()
    with zipfile.ZipFile(wheel) as archive:
        digest = hashlib.sha256(
            archive.read("flaskteroids/cli/flaskteroids.py")
        ).hexdigest()
        for name in (
            "flaskteroids/cli/templates/.github/workflows/test.yml.mako",
            "flaskteroids/cli/templates/bin/flask.mako",
            "flaskteroids/cli/generators/model/templates/model.py.mako",
        ):
            assert name in archive.namelist(), name
    imported = run(
        root / ".venv/bin/python",
        "-c",
        "import flaskteroids, hashlib; from pathlib import Path; print(flaskteroids.__version__); print(hashlib.sha256((Path(flaskteroids.__file__).parent / 'cli/flaskteroids.py').read_bytes()).hexdigest())",
        cwd=root,
    )
    assert digest in imported.stdout, "App did not install the supplied candidate"
    pristine = run("bin/flask", "test", "-v", cwd=root)
    assert "HealthControllerTest::test_should_get_health PASSED" in pristine.stdout
    empty = run("bin/flask", "test:system", "-v", cwd=root)
    assert "No tests collected" in empty.stdout
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    server = subprocess.Popen(
        [str(root / "bin/flask"), "run", "--port", str(port)],
        cwd=work,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/up/", timeout=1
                ) as response:
                    assert response.status == 200
                break
            except OSError:
                if server.poll() is not None:
                    raise RuntimeError("Development server failed to start") from None
                time.sleep(0.1)
        else:
            raise RuntimeError("Health request timed out")
    finally:
        server.terminate()
        server.wait(timeout=10)
    credentials = (root / "config/credentials.yml.enc").read_bytes()
    key = (root / "config/master.key").read_bytes()
    run("bin/setup", cwd=root)
    run(
        "bin/flask",
        "generate",
        "scaffold",
        "Post",
        "title:string",
        "content:text",
        cwd=root,
    )
    run("bin/flask", "db:prepare", cwd=root)
    record = run(
        root / ".venv/bin/python",
        "-c",
        "from wsgi import app; from app.models.post import Post\nwith app.app_context():\n    post = Post.create(title='Retained', content='Content')\n    assert post.id\n    assert Post.find(post.id).title == 'Retained'\nclient = app.test_client()\nassert client.get('/posts/').status_code == 200\nresponse = client.get('/posts/', headers={'Accept':'application/json'})\nassert response.status_code == 200\nassert response.get_json()[0]['title'] == 'Retained'",
        cwd=root,
    )
    assert record.returncode == 0
    run("bin/setup", cwd=root)
    run(
        root / ".venv/bin/python",
        "-c",
        "from wsgi import app; from app.models.post import Post\nwith app.app_context():\n    assert Post.where(title='Retained').count() == 1",
        cwd=root,
    )
    assert (root / "config/credentials.yml.enc").read_bytes() == credentials
    assert (root / "config/master.key").read_bytes() == key
    tests = run("bin/flask", "test", "-v", cwd=root)
    assert "test_should_create_post PASSED" in tests.stdout
    assert "test_should_destroy_post PASSED" in tests.stdout
    if args.browser:
        run(root / ".venv/bin/playwright", "install", "chromium", cwd=root)
        browser = run("bin/flask", "test:system", "-v", cwd=root)
        assert "test_visiting_the_index PASSED" in browser.stdout
    run("uv", "sync", "--locked", cwd=root)
    metadata = root / "pyproject.toml"
    original = metadata.read_text()
    metadata.write_text(original.replace('"gunicorn",', '"gunicorn", "httpx",'))
    assert run("uv", "sync", "--locked", cwd=root, success=False).returncode != 0
    metadata.write_text(original)
    lock = root / "uv.lock"
    lock.rename(root / "saved.lock")
    assert run("uv", "sync", "--locked", cwd=root, success=False).returncode != 0
    (root / "saved.lock").rename(lock)
    # Controlled PATH includes Git and Bash but deliberately no uv.
    no_uv = work / "no-uv"
    no_uv.mkdir()
    for executable in ("bash", "git"):
        (no_uv / executable).symlink_to(shutil.which(executable))
    run(command, "new", "deferred", "--skip-install", env={"PATH": str(no_uv)})
    deferred = work / "deferred"
    assert not (deferred / ".venv").exists()
    assert not (deferred / "uv.lock").exists()
    assert not (deferred / "storage/development.sqlite3").exists()
    assert (deferred / "db/migrate/versions/.keep").exists()
    run("bin/setup", cwd=deferred)
    run("bin/flask", "test", "-v", cwd=deferred)
    # Isolate authentication/attachments/mailers from the pristine/scaffold example.
    for name, generators in {
        "mail": [("mailer", "Notifications", "welcome")],
        "auth": [("authentication",)],
        "uploads": [("scaffold", "Member", "name:string", "avatar:attachment")],
    }.items():
        run(command, "new", name)
        app = work / name
        for generator_args in generators:
            run("bin/flask", "generate", *generator_args, cwd=app)
        if name == "uploads":
            run("bin/flask", "attachments:install", cwd=app)
        run("bin/flask", "db:prepare", cwd=app)
        result = run("bin/flask", "test", "-v", cwd=app)
        assert "No tests collected" not in result.stdout
        if args.browser and name == "uploads":
            result = run("bin/flask", "test:system", "-v", cwd=app)
            assert "test_visiting_the_index PASSED" in result.stdout
    print(
        json.dumps(
            {
                "work_dir": str(work),
                "candidate_sha256": digest,
                "browser_exercised": args.browser,
            }
        )
    )


if __name__ == "__main__":
    main()
