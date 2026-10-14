"""Opt-in Docker runtime acceptance for an already built generated-app image.

python scripts/accept_docker_app.py --app-root PATH --image IMAGE
The image must contain a Post scaffold and matching encrypted credentials.
Supply candidate artifacts at build time through a test-only reachable source.
"""

import argparse
import hashlib
import os
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    name = "flaskteroids-acceptance-" + uuid4().hex[:8]
    volume = name + "-storage"

    def run(*command, success=True):
        result = subprocess.run(
            ["docker", *map(str, command)], capture_output=True, text=True, check=False
        )
        print("+ docker", " ".join(map(str, command)), flush=True)
        print(result.stdout, end="")
        print(result.stderr, end="")
        if success and result.returncode:
            raise RuntimeError(f"Docker command failed ({result.returncode})")
        return result

    with tempfile.TemporaryDirectory(
        prefix="flaskteroids-runtime-secrets-"
    ) as directory:
        secret_file = Path(directory) / ".env.production"
        secret_file.touch(mode=0o600)
        secret_file.write_text(
            "FLASKTEROIDS_MASTER_KEY="
            + (args.app_root / "config/master.key").read_text().strip()
            + "\n"
        )
        runtime = ["--env-file", str(secret_file), "-v", f"{volume}:/app/storage"]
        run("volume", "create", volume)
        try:
            bypass = run(
                "run",
                "--rm",
                args.image,
                "bash",
                "-c",
                "test ! -e config/master.key && test ! -e .git && test ! -e .env.production && test ! -e storage/development.sqlite3 && test ! -e .venv/bin/pip && test -x bin/flask && test -w storage && test $(id -u) -ne 0 && echo bypass",
            )
            assert "bypass" in bypass.stdout
            assert "alembic" not in bypass.stderr
            host_source = next(
                (args.app_root / ".venv/lib").glob(
                    "python*/site-packages/flaskteroids/cli/flaskteroids.py"
                )
            )
            candidate_hash = hashlib.sha256(host_source.read_bytes()).hexdigest()
            imported = run(
                "run",
                "--rm",
                args.image,
                "/app/.venv/bin/python",
                "-c",
                "import flaskteroids, hashlib; from pathlib import Path; print(flaskteroids.__version__); print(hashlib.sha256((Path(flaskteroids.__file__).parent / 'cli/flaskteroids.py').read_bytes()).hexdigest())",
            )
            assert candidate_hash in imported.stdout
            run("run", "--rm", *runtime, args.image, "celery", "-A", "jobs", "report")
            for extra in ([], ["-e", "FLASKTEROIDS_MASTER_KEY=wrong-key"]):
                result = run("run", "--rm", *extra, args.image, success=False)
                assert result.returncode != 0
                assert "Listening at" not in result.stdout + result.stderr
            result = run(
                "run",
                "--rm",
                *runtime,
                "-e",
                "DATABASE_URL=sqlite:///absent/db.sqlite3",
                args.image,
                success=False,
            )
            assert result.returncode != 0
            assert "Listening at" not in result.stdout + result.stderr
            for attempt in range(2):
                run(
                    "run",
                    "-d",
                    "--name",
                    name,
                    "-p",
                    "127.0.0.1::8000",
                    *runtime,
                    args.image,
                )
                port = run("port", name, "8000/tcp").stdout.strip().rsplit(":", 1)[1]
                for _ in range(100):
                    try:
                        with urllib.request.urlopen(
                            f"http://127.0.0.1:{port}/up/", timeout=1
                        ) as response:
                            assert response.status == 200
                        break
                    except OSError:
                        time.sleep(0.1)
                else:
                    run("logs", name)
                    raise RuntimeError("Container health request timed out")
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/posts/", timeout=2
                ) as response:
                    assert response.status == 200
                if attempt == 0:
                    run(
                        "exec",
                        name,
                        "/app/.venv/bin/python",
                        "-c",
                        "from wsgi import app; from app.models.post import Post\nwith app.app_context():\n    assert Post.create(title='Persistent', content='Content').id",
                    )
                else:
                    run(
                        "exec",
                        name,
                        "/app/.venv/bin/python",
                        "-c",
                        "from wsgi import app; from app.models.post import Post\nwith app.app_context():\n    assert Post.where(title='Persistent').count() == 1",
                    )
                run(
                    "exec",
                    name,
                    "bash",
                    "-c",
                    "test -w /app/storage && test $(id -u) -ne 0",
                )
                run("stop", "--time", "10", name)
                logs = run("logs", name)
                assert "Handling signal: term" in logs.stderr
                run("rm", name)
            run("run", "--rm", *runtime, args.image, "/app/bin/release", "migrate")
            run(
                "run",
                "--rm",
                *runtime,
                args.image,
                "/app/.venv/bin/python",
                "-c",
                "import sqlite3\nwith sqlite3.connect('storage/production.sqlite3') as db:\n    db.execute(\"UPDATE alembic_version SET version_num = 'unknown'\")",
            )
            failed = run("run", "--rm", *runtime, args.image, success=False)
            assert failed.returncode != 0
            assert "unknown" in failed.stdout + failed.stderr
            assert "Listening at" not in failed.stdout + failed.stderr
            print(
                "Docker runtime acceptance passed; worker app loading only (no broker/job execution)."
            )
        finally:
            run("rm", "-f", name, success=False)
            run("volume", "rm", volume, success=False)
            os.chmod(secret_file, 0o600)


if __name__ == "__main__":
    main()
