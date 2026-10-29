import json

import pytest
from click.testing import CliRunner
from flask import render_template_string
from flask.cli import cli
from markupsafe import Markup

from flaskteroids.assets import AssetError, AssetPipeline
from flaskteroids.helpers import (
    asset_path,
    importmap_digest,
    javascript_import_module_tag,
    javascript_importmap_tags,
    javascript_inline_importmap_tag,
    javascript_module_preload_tag,
)
from tests.assertions import HTML


@pytest.fixture
def module_root(asset_root):
    files = {
        "config/importmap.py": 'def register(importmap):\n    importmap.enable_integrity()\n    importmap.pin("application")\n    importmap.pin_all_from("app/javascript/lib", under="lib")\n    importmap.pin("optional", preload=False)\n',
        "app/javascript/application.js": 'import { value } from "lib/example"; window.result = value;',
        "app/javascript/lib/example.js": "export const value = 42;",
        "vendor/javascript/optional.js": "export default 1;",
    }
    for name, content in files.items():
        path = asset_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return asset_root


@pytest.mark.parametrize("environment", ["development", "test", "production"])
def test_module_helpers_use_the_asset_pipeline_and_preload_metadata(
    module_root, asset_application, environment
):
    if environment == "production":
        AssetPipeline(module_root).precompile()
    app = asset_application(environment)
    with app.test_request_context():
        markup = javascript_importmap_tags(nonce='trusted"nonce')
        assert isinstance(markup, Markup)
        html = HTML(markup)
        assert html.has(
            "script",
            type="importmap",
            nonce='trusted"nonce',
            **{"data-turbo-track": "reload"},
        )
        assert html.has("script", type="module", nonce='trusted"nonce')
        for name in ("application.js", "lib/example.js"):
            url = asset_path(name)
            assert html.has(
                "link", rel="modulepreload", href=url, nonce='trusted"nonce'
            )
            response = app.test_client().get(url)
            assert response.status_code == 200
            assert response.mimetype in {"application/javascript", "text/javascript"}
        assert not html.has("link", href=asset_path("optional.js"))
        assert app.test_client().get(asset_path("optional.js")).status_code == 200
        assert render_template_string("{{ javascript_importmap_tags() }}").startswith(
            "<script"
        )


def test_source_and_vendor_modules_share_the_static_endpoint(
    module_root, asset_application
):
    app = asset_application()
    client = app.test_client()
    assert client.get("/assets/lib/example.js").text == "export const value = 42;"
    response = client.get("/assets/optional.js")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert client.head("/assets/optional.js").data == b""
    assert (
        client.get("/assets/optional.js", headers={"Range": "bytes=0-5"}).status_code
        == 206
    )


def test_production_integrity_hashes_the_served_bytes(module_root, asset_application):
    pipeline = AssetPipeline(module_root)
    pipeline.precompile()
    app = asset_application("production")
    with app.test_request_context():
        html = HTML(javascript_importmap_tags())
        url = asset_path("application.js")
        assert html.has(
            "link",
            href=url,
            integrity=pipeline.asset_integrity("application.js", compiled=True),
        )


def test_production_map_cache_separates_deployment_prefixes(
    module_root, asset_application
):
    AssetPipeline(module_root).precompile()
    app = asset_application("production")
    for prefix in ("", "/mounted", ""):
        with app.test_request_context(environ_overrides={"SCRIPT_NAME": prefix}):
            assert HTML(javascript_importmap_tags()).has(
                "link", href=asset_path("application.js")
            )


def test_development_reload_handles_config_edits_and_module_additions(
    module_root, asset_application
):
    app = asset_application()
    with app.test_request_context():
        assert "lib/example" in str(javascript_importmap_tags())
    (module_root / "app/javascript/lib/new.js").write_text("export {};")
    (module_root / "config/importmap.py").write_text(
        'def register(importmap):\n    importmap.pin("application")\n    importmap.pin_all_from("app/javascript/lib", under="utilities", to="lib")\n'
    )
    with app.test_request_context():
        markup = str(javascript_importmap_tags())
        assert "utilities/new" in markup
        assert '"lib/example"' not in markup
        assert '"optional"' not in markup


def test_bootless_json_matches_runtime_map_urls(module_root, asset_application):
    vendor = module_root / "vendor/javascript/@scope--library.js"
    vendor.write_text("export {};")
    config = module_root / "config/importmap.py"
    config.write_text(
        config.read_text()
        + '    importmap.pin("@scope/library", to="@scope--library.js")\n'
    )
    result = CliRunner().invoke(cli, ["importmap", "--root", str(module_root), "json"])
    assert result.exit_code == 0, result.output
    with asset_application().test_request_context():
        html = HTML(javascript_inline_importmap_tag())
        assert json.loads(html.scripts[0]["content"]) == json.loads(result.output)


def test_helpers_escape_script_data_and_module_names():
    value = "x</script><script>alert(1)</script>"
    markup = javascript_inline_importmap_tag(
        {"imports": {value: "https://example.test/module.js"}}
    )
    assert str(markup).count("</script>") == 1
    assert value in json.loads(HTML(markup).text)["imports"]
    module = javascript_import_module_tag(value, nonce="trusted")
    assert str(module).count("</script>") == 1
    assert HTML(module).has("script", type="module", nonce="trusted")
    assert HTML(javascript_module_preload_tag('/assets/a"&.js')).has(
        "link", href='/assets/a"&.js'
    )


def test_html_map_digest_changes_with_production_module_urls(
    module_root, asset_application
):
    pipeline = AssetPipeline(module_root)
    pipeline.precompile()
    with asset_application("production").test_request_context():
        first = importmap_digest()
        assert importmap_digest() == first
    (module_root / "app/javascript/lib/example.js").write_text(
        "export const value = 43;"
    )
    pipeline.precompile()
    with asset_application("production").test_request_context():
        assert importmap_digest() != first


@pytest.mark.parametrize("source", ["app/javascript", "vendor/javascript"])
def test_application_turbo_assets_override_framework_source(
    module_root, asset_application, source
):
    override = module_root / source / "turbo.js"
    override.write_text("export const applicationOwned = true;")
    pipeline = AssetPipeline(module_root)
    assert pipeline.source_file("turbo.js") == override
    manifest = pipeline.precompile()
    assert (
        pipeline.output / manifest["turbo.js"]
    ).read_bytes() == override.read_bytes()
    with asset_application().test_request_context():
        url = asset_path("turbo.js")
    assert asset_application().test_client().get(url).data == override.read_bytes()


def test_helpers_reject_unpinned_entrypoints(module_root, asset_application):
    with (
        asset_application().test_request_context(),
        pytest.raises(ValueError, match="Entrypoint"),
    ):
        javascript_importmap_tags("missing")


@pytest.mark.parametrize("location", ["app/javascript", "vendor/javascript"])
def test_javascript_sources_reject_symlink_replacement(
    module_root, asset_application, location
):
    app = asset_application()
    directory = module_root / location
    directory.rename(module_root / "previous")
    directory.symlink_to(module_root / "private", target_is_directory=True)
    assert app.test_client().get("/assets/application.js").status_code == 404
    with app.test_request_context(), pytest.raises(AssetError):
        asset_path("application.js")


def test_duplicate_source_assets_fail_development_and_precompilation(
    module_root, asset_application
):
    (module_root / "vendor/javascript/application.js").write_text("export {};")
    with pytest.raises(AssetError, match="Duplicate"):
        AssetPipeline(module_root).precompile()
    with (
        asset_application().test_request_context(),
        pytest.raises(AssetError, match="Duplicate"),
    ):
        asset_path("application.js")


def test_javascript_compilation_keeps_logical_imports_unchanged(module_root):
    pipeline = AssetPipeline(module_root)
    first = pipeline.precompile()
    source = module_root / "app/javascript/application.js"
    assert (
        pipeline.output / first["application.js"]
    ).read_bytes() == source.read_bytes()
    (module_root / "app/javascript/lib/example.js").write_text(
        "export const value = 43;"
    )
    second = pipeline.precompile()
    assert first["application.js"] == second["application.js"]
    assert first["lib/example.js"] != second["lib/example.js"]


@pytest.mark.parametrize(
    "name", [".keep", "../private.js", "app/javascript/application.js"]
)
def test_module_sources_reject_hidden_and_project_paths(
    module_root, asset_application, name
):
    assert asset_application().test_client().get(f"/assets/{name}").status_code == 404
