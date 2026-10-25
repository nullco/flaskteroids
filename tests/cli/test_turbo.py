import json
from importlib.resources import files

from tests.assertions import HTML


def test_new_application_includes_the_pinned_runtime_and_license(generated_app_factory):
    root, _run = generated_app_factory("turbo_assets")
    resources = files("flaskteroids.turbo").joinpath("assets")
    for name in ("turbo.js", "TURBO-LICENSE", "README.md"):
        assert (root / "app/assets/turbo" / name).read_bytes() == resources.joinpath(
            name
        ).read_bytes()
    layout = (root / "app/views/layouts/application.html").read_text()
    assert "cdn.jsdelivr.net" not in layout
    assert "asset_path('turbo/turbo.js')" in layout
    assert HTML(layout).has("meta", name="csrf-token")


def test_install_migrates_the_original_cdn_without_replacing_customizations(
    generated_app_factory,
):
    root, run = generated_app_factory("turbo_migration")
    runtime = root / "app/assets/turbo/turbo.js"
    runtime.write_text("/* application-owned Turbo customization */")
    layout = root / "app/views/layouts/application.html"
    layout.write_text(
        layout.read_text()
        .replace(
            "{{ asset_path('turbo/turbo.js') }}",
            "https://cdn.jsdelivr.net/npm/@hotwired/turbo@latest/dist/turbo.es2017-esm.min.js",
        )
        .replace("<script defer", '<script defer nonce="custom-nonce"')
        .replace('    <meta name="csrf-token" content="{{ csrf_token() }}">\n', "")
    )
    run("turbo:install")
    migrated = layout.read_text()
    assert "cdn.jsdelivr.net" not in migrated
    assert "asset_path('turbo/turbo.js')" in migrated
    assert HTML(migrated).has("script", nonce="custom-nonce")
    assert HTML(migrated).has("meta", name="csrf-token")
    assert runtime.read_text() == "/* application-owned Turbo customization */"
    run("turbo:install")
    assert layout.read_text() == migrated
    assert runtime.read_text() == "/* application-owned Turbo customization */"


def test_force_install_refreshes_the_app_owned_runtime(generated_app_factory):
    root, run = generated_app_factory("turbo_refresh")
    runtime = root / "app/assets/turbo/turbo.js"
    runtime.write_text("/* local customization */")
    run("turbo:install", "--force")
    assert (
        runtime.read_bytes()
        == files("flaskteroids.turbo").joinpath("assets/turbo.js").read_bytes()
    )


def test_custom_runtime_layout_receives_instructions_without_duplicate_scripts(
    generated_app_factory,
):
    root, run = generated_app_factory("turbo_custom")
    layout = root / "app/views/layouts/application.html"
    customized = layout.read_text().replace(
        "{{ asset_path('turbo/turbo.js') }}", "https://example.test/custom/turbo.js"
    )
    layout.write_text(customized)
    result = run("turbo:install")
    assert "asset_path('turbo/turbo.js')" in result.stdout
    assert layout.read_text() == customized


def test_turbo_runtime_is_fingerprinted_by_the_production_asset_pipeline(
    generated_app_factory,
):
    root, run = generated_app_factory("turbo_production")
    run("assets:precompile")
    manifest = json.loads((root / "public/assets/.manifest.json").read_text())
    name = manifest["turbo/turbo.js"]
    assert name.startswith("turbo/turbo-")
    assert (root / "public/assets" / name).read_bytes() == (
        root / "app/assets/turbo/turbo.js"
    ).read_bytes()
