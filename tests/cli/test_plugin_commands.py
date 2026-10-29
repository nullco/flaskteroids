import json
from pathlib import Path

import pytest
from click.testing import CliRunner


@pytest.mark.generated_app
def test_new_creates_application_without_loading_existing_application(
    bootless_cli, tmp_path
):
    root = tmp_path / "weblog"

    result = CliRunner().invoke(bootless_cli, ["new", str(root), "--skip-install"])

    assert result.exit_code == 0, result.output
    assert (root / "config/application.py").is_file()


def test_asset_plugin_builds_without_loading_application(bootless_cli, tmp_path):
    source = tmp_path / "app/assets/stylesheets"
    source.mkdir(parents=True)
    (source / "application.css").write_text("body { color: red; }")

    result = CliRunner().invoke(
        bootless_cli, ["assets:precompile", "--root", str(tmp_path)]
    )

    assert result.exit_code == 0, result.output
    manifest = json.loads((tmp_path / "public/assets/.manifest.json").read_text())
    assert "stylesheets/application.css" in manifest


def test_importmap_plugin_resolves_without_loading_application(bootless_cli, tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config/importmap.py").write_text(
        'def register(importmap):\n    importmap.pin("example", to="https://example.com/example.js")\n'
    )

    result = CliRunner().invoke(
        bootless_cli, ["importmap", "--root", str(tmp_path), "json"]
    )

    assert result.exit_code == 0, result.output
    assert (
        json.loads(result.output)["imports"]["example"]
        == "https://example.com/example.js"
    )


def test_agent_skills_plugin_locates_guidance_without_loading_application(bootless_cli):
    result = CliRunner().invoke(bootless_cli, ["agent-skills", "path"])

    assert result.exit_code == 0, result.output
    assert (Path(result.output.strip()) / "using-flaskteroids/SKILL.md").is_file()
