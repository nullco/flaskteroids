import json
from importlib.resources import files

from flaskteroids.assets import AssetPipeline
from flaskteroids.importmaps import ImportMap
from tests.assertions import HTML


def test_new_application_pins_framework_turbo_without_copying_runtime(
    generated_app_factory,
):
    root, _run = generated_app_factory("turbo_assets")
    pipeline = AssetPipeline(root)
    pins = ImportMap.load(root).resolve(pipeline.source_name).to_dict()["imports"]
    assert pins["@hotwired/turbo"] == "turbo.js"
    runtime = pipeline.source_file("turbo.js")
    assert not runtime.is_relative_to(root)
    assert (
        runtime.read_bytes()
        == files("flaskteroids_turbo").joinpath("assets/turbo.js").read_bytes()
    )
    assert not list((root / "vendor/javascript").glob("*.js"))
    assert not (root / "app/assets/turbo").exists()
    assert (
        root / "app/javascript/application.js"
    ).read_text().strip() == 'import "@hotwired/turbo"'
    layout = (root / "app/views/layouts/application.html").read_text()
    assert "javascript_importmap_tags()" in layout
    assert HTML(layout).has("meta", name="csrf-token")


def test_install_preserves_application_runtime_override(generated_app_factory):
    root, run = generated_app_factory("turbo_override")
    runtime = root / "vendor/javascript/turbo.js"
    runtime.write_text("/* local ESM customization */")
    run("turbo:install")
    assert AssetPipeline(root).source_file("turbo.js") == runtime
    assert runtime.read_text() == "/* local ESM customization */"


def test_custom_runtime_layout_receives_instructions_without_duplicate_scripts(
    generated_app_factory,
):
    root, run = generated_app_factory("turbo_custom")
    layout = root / "app/views/layouts/application.html"
    customized = layout.read_text().replace(
        "{{ javascript_importmap_tags() }}",
        '<script src="https://example.test/custom/turbo.js"></script>',
    )
    layout.write_text(customized)
    result = run("turbo:install")
    assert "javascript_importmap_tags()" in result.stdout
    assert layout.read_text() == customized


def test_framework_turbo_is_included_in_production_precompilation(
    generated_app_factory,
):
    root, run = generated_app_factory("turbo_production")
    run("assets:precompile")
    manifest = json.loads((root / "public/assets/.manifest.json").read_text())
    name = manifest["turbo.js"]
    assert name.startswith("turbo-")
    assert (root / "public/assets" / name).read_bytes() == AssetPipeline(
        root
    ).source_file("turbo.js").read_bytes()
