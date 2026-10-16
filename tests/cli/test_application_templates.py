import ast
import tomllib

import pytest
import yaml
from click.testing import CliRunner

from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.cli.flaskteroids import cli
from flaskteroids.credentials import decrypt


@pytest.fixture
def generated_app(tmp_path, mocker):
    mocker.patch.object(ArtifactsBuilder, "run")
    mocker.patch.object(ArtifactsBuilder, "python_run")
    root = tmp_path / "weblog"
    result = CliRunner().invoke(cli, ["new", str(root), "--skip-install"])
    assert result.exit_code == 0, result.output
    return root


def test_generated_application_includes_source_configuration_and_credentials(
    generated_app,
):
    for path in generated_app.rglob("*.py"):
        ast.parse(path.read_text(), filename=str(path))
    metadata = tomllib.loads((generated_app / "pyproject.toml").read_text())
    assert metadata["project"]["name"].endswith("weblog")
    assert metadata["project"]["requires-python"] == ">=3.12"
    database = yaml.safe_load((generated_app / "config/database.yml").read_text())
    assert database["development"]["database"] == "storage/development.sqlite3"
    key = (generated_app / "config/master.key").read_text().strip()
    encrypted = (generated_app / "config/credentials.yml.enc").read_text()
    credentials = yaml.safe_load(decrypt(encrypted, key))
    assert len(credentials["secret_key_base"]) == 128
    assert credentials["secret_key_base"] not in encrypted
    assert (
        "config.require_master_key = True"
        in (generated_app / "config/environments/production.py").read_text()
    )
    layout = (generated_app / "app/views/layouts/application.html").read_text()
    assert "{%" in layout
    for name in ("setup", "release"):
        script = generated_app / "bin" / name
        assert script.read_bytes().startswith(b"#!/usr/bin/env bash\n")
        assert script.stat().st_mode & 0o111
        assert script.read_bytes().endswith(b"\n")
