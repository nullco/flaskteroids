import base64
import os
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from flaskteroids.cli.flaskteroids import cli

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
    return root


def run(root, *args, environment="development"):
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("FLASK", "DATABASE", "SECRET_KEY"))
    }
    env |= {
        "PYTHONPATH": str(FRAMEWORK_ROOT),
        "FLASK_ENV": environment,
        "DATABASE_URL": "sqlite:///:memory:",
    }
    return subprocess.run(
        args, cwd=root.parent, env=env, capture_output=True, text=True, check=False
    )


def test_generated_launcher_precompiles_without_boot_or_runtime_secrets(
    generated_assets_app,
):
    root = generated_assets_app
    (root / "config/application.py").write_text(
        'raise AssertionError("application booted")'
    )
    (root / "config/master.key").unlink()
    (root / "config/initializers/fail.py").write_text(
        'raise AssertionError("initializer ran")'
    )
    result = run(
        root, str(root / "bin/flask"), "assets:precompile", environment="production"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Precompiled 2 assets" in result.stdout
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
        "-c",
        f"""
import sys
sys.path.insert(0, {str(root)!r})
from flask import render_template
from wsgi import app
from flaskteroids.helpers import asset_path
with app.test_request_context():
    html = render_template("layouts/application.html")
    url = asset_path("application.css")
    assert f'href="{{url}}"' in html
    assert 'data-turbo-track="reload"' in html
response = app.test_client().get(url)
assert response.status_code == 200
assert response.mimetype == "text/css"
assert b"color: rgb(255, 0, 0)" in response.data
assert ('logo-' in response.text) == {environment == "production"!r}
assert ('application-' in url) == {environment == "production"!r}
""",
        environment=environment,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_generated_docker_compiles_after_copy_and_before_runtime_user(
    generated_assets_app,
):
    root = generated_assets_app
    dockerfile = (root / "Dockerfile").read_text()
    assert dockerfile.index("COPY . .") < dockerfile.index(
        "RUN bin/flask assets:precompile"
    )
    assert dockerfile.index("RUN bin/flask assets:precompile") < dockerfile.index(
        "USER app"
    )
    for name in (".gitignore", ".dockerignore"):
        assert "public/assets/" in (root / name).read_text()


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
        "-c",
        f"""
import sys
sys.path.insert(0, {str(generated_assets_app)!r})
from wsgi import app
from flask import render_template
from threading import Thread
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright
import os
import shutil
app.add_url_rule('/asset-test/', view_func=lambda: render_template('layouts/application.html'))
server = make_server('127.0.0.1', 0, app)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH') or shutil.which('google-chrome'),
        )
        page = browser.new_page()
        page.route('https://cdn.jsdelivr.net/**', lambda route: route.abort())
        page.goto(f'http://127.0.0.1:{{server.server_port}}/asset-test/')
        href = page.locator('link[rel="stylesheet"]').get_attribute('href')
        assert href.startswith('/assets/stylesheets/application')
        assert ('application-' in href) == {environment == "production"!r}
        assert page.locator('body').evaluate('(body) => getComputedStyle(body).color') == 'rgb(255, 0, 0)'
        background = page.locator('body').evaluate('(body) => getComputedStyle(body).backgroundImage')
        assert ('logo-' in background) == {environment == "production"!r}
        assert page.evaluate('''async () => {{
            const image = new Image();
            image.src = getComputedStyle(document.body).backgroundImage.slice(5, -2);
            await image.decode();
            return image.naturalWidth;
        }}''') == 1
        browser.close()
finally:
    server.shutdown()
    thread.join(timeout=5)
""",
        environment=environment,
    )
    assert result.returncode == 0, result.stdout + result.stderr
