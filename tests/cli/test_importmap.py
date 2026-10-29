import json
import os
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner
from flask.cli import cli

from flaskteroids.assets import AssetPipeline
from flaskteroids.importmaps import ImportMap
from flaskteroids.importmaps.installation import install
from flaskteroids.importmaps.packages import HTTPClient
from tests.assertions import HTML


@pytest.fixture
def importmap_project(tmp_path):
    install(tmp_path)
    return tmp_path


def invoke(root, *args):
    return CliRunner().invoke(cli, ["importmap", "--root", str(root), *args])


@pytest.fixture
def package_network(mocker):
    resolve = mocker.patch.object(
        HTTPClient,
        "json",
        return_value={
            "map": {
                "imports": {
                    "@scope/library": "https://ga.jspm.io/npm:@scope/library@1.2.3/index.js"
                }
            }
        },
    )
    download = mocker.patch.object(
        HTTPClient, "request", return_value=b"export const value = 42;"
    )
    return resolve, download


def test_pin_packages_and_unpin_through_the_public_cli(
    importmap_project, package_network
):
    result = invoke(importmap_project, "pin", "@scope/library", "--no-preload")
    assert result.exit_code == 0, result.output
    imports = ImportMap.load(importmap_project).resolve(str)
    assert imports.to_dict()["imports"]["@scope/library"] == "@scope--library.js"
    assert all(pin.name != "@scope/library" for pin in imports.preloads())
    result = invoke(importmap_project, "packages")
    assert result.exit_code == 0
    assert "@scope/library 1.2.3" in result.output
    result = invoke(importmap_project, "unpin", "@scope/library")
    assert result.exit_code == 0, result.output
    assert (
        "@scope/library"
        not in ImportMap.load(importmap_project).resolve(str).to_dict()["imports"]
    )


@pytest.mark.parametrize("command", ["update", "pristine"])
def test_maintenance_commands_keep_pin_options(
    importmap_project, package_network, command
):
    assert (
        invoke(importmap_project, "pin", "@scope/library", "--no-preload").exit_code
        == 0
    )
    result = invoke(importmap_project, command)
    assert result.exit_code == 0, result.output
    pin = next(
        pin
        for pin in ImportMap.load(importmap_project).pins()
        if pin.name == "@scope/library"
    )
    assert pin.preload is False


def test_cli_reports_resolution_errors_without_a_traceback(
    importmap_project, package_network
):
    resolve, _download = package_network
    resolve.return_value = {"error": "not found"}
    result = invoke(importmap_project, "pin", "missing")
    assert result.exit_code == 1
    assert "not found" in result.output
    assert "Traceback" not in result.output


def test_cli_reports_missing_configuration_with_its_path(tmp_path):
    result = invoke(tmp_path, "pin", "library")
    assert result.exit_code == 1
    assert "config/importmap.py" in result.output


@pytest.mark.parametrize("environment", ["development", "production", "staging"])
def test_json_command_resolves_framework_and_application_assets(
    importmap_project, environment
):
    if environment != "development":
        AssetPipeline(importmap_project).precompile()
    result = invoke(
        importmap_project,
        "json",
        "--environment",
        environment,
        "--prefix",
        "/mounted/assets",
    )
    assert result.exit_code == 0, result.output
    mapping = json.loads(result.output)["imports"]
    assert mapping["@hotwired/turbo"].startswith("/mounted/assets/turbo")
    assert ("turbo-" in mapping["@hotwired/turbo"]) == (environment != "development")


@pytest.mark.parametrize(
    "prefix", ["/", "//assets", "/assets?x=1", "/assets/../private"]
)
def test_json_command_rejects_invalid_asset_prefixes(importmap_project, prefix):
    result = invoke(importmap_project, "json", "--prefix", prefix)
    assert result.exit_code == 1


def test_generated_launcher_runs_without_application_boot_or_secrets(
    generated_app_factory,
):
    root, _run = generated_app_factory("importmap_launcher")
    (root / "config/application.py").write_text(
        'raise AssertionError("application booted")'
    )
    (root / "config/master.key").unlink()
    env = {
        key: value for key, value in os.environ.items() if not key.startswith("FLASK")
    }
    env["PYTHONPATH"] = str(Path(__file__).parents[2])
    result = subprocess.run(
        [str(root / "bin/importmap"), "json"],
        cwd=root.parent,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["imports"]["@hotwired/turbo"] == "/assets/turbo.js"


def test_api_generation_omits_importmap_artifacts(generated_app_factory):
    root, _run = generated_app_factory("importmap_api", "--api")
    assert not (root / "config/importmap.py").exists()
    assert not (root / "app/javascript").exists()
    assert not (root / "vendor/javascript").exists()
    assert not (root / "bin/importmap").exists()


def test_installer_preserves_application_configuration_and_entrypoint(
    importmap_project,
):
    config = importmap_project / "config/importmap.py"
    entrypoint = importmap_project / "app/javascript/application.js"
    config.write_text('def register(importmap):\n    importmap.pin("custom")\n')
    entrypoint.write_text('import "custom"\n')
    before = (config.read_bytes(), entrypoint.read_bytes())
    install(importmap_project)
    assert (config.read_bytes(), entrypoint.read_bytes()) == before


def test_installer_adds_module_setup_to_a_fresh_layout_once(importmap_project):
    layout = importmap_project / "app/views/layouts/application.html"
    layout.parent.mkdir(parents=True)
    layout.write_text("<html><head></head><body></body></html>")
    install(importmap_project)
    configured = layout.read_text()
    assert "javascript_importmap_tags()" in configured
    assert HTML(configured).has("meta", name="csrf-token")
    install(importmap_project)
    assert layout.read_text() == configured


def test_application_install_command_restores_missing_conventions(
    generated_app_factory,
):
    root, run = generated_app_factory("importmap_install")
    for name in (
        "config/importmap.py",
        "app/javascript/application.js",
        "bin/importmap",
    ):
        (root / name).unlink()
    result = run("importmap:install")
    assert (root / "bin/importmap").stat().st_mode & 0o111
    assert (
        ImportMap.load(root).resolve(str).to_dict()["imports"]["@hotwired/turbo"]
        == "turbo.js"
    )
    assert "Traceback" not in result.stdout
