import json

import pytest

from flaskteroids.assets import AssetError
from flaskteroids.importmaps import ImportMap, ImportmapError
from flaskteroids.importmaps.map import script_json


@pytest.fixture
def importmap(tmp_path):
    return ImportMap(tmp_path)


def test_pins_resolve_local_assets_and_preserve_external_urls(importmap):
    importmap.pin("application")
    importmap.pin("library", to="https://example.test/library@1.2.3.js")
    calls = []

    def resolve(name):
        calls.append(name)
        return f"/assets/{name}"

    assert importmap.resolve(resolve).to_dict() == {
        "imports": {
            "application": "/assets/application.js",
            "library": "https://example.test/library@1.2.3.js",
        }
    }
    assert calls == ["application.js"]


def test_directory_pins_expand_nested_modules_and_index_conventions(
    importmap, tmp_path
):
    root = tmp_path / "app/javascript/controllers"
    for name in (
        "index.js",
        "hello.js",
        "nested/index.mjs",
        "nested/example.js",
        ".hidden.js",
        "readme.txt",
    ):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("export {}")
    importmap.pin_all_from("app/javascript/controllers", under="controllers")
    result = importmap.resolve(lambda name: f"/assets/{name}").to_dict()["imports"]
    assert result == {
        "controllers": "/assets/controllers/index.js",
        "controllers/hello": "/assets/controllers/hello.js",
        "controllers/nested": "/assets/controllers/nested/index.mjs",
        "controllers/nested/example": "/assets/controllers/nested/example.js",
    }
    (root / "new.js").write_text("export {}")
    assert "controllers/new" in importmap.resolve(str).to_dict()["imports"]
    (root / "hello.js").unlink()
    assert "controllers/hello" not in importmap.resolve(str).to_dict()["imports"]


def test_directory_pins_allow_separate_logical_and_asset_paths(importmap, tmp_path):
    root = tmp_path / "app/javascript/lib"
    root.mkdir(parents=True)
    (root / "example.js").write_text("export {}")
    importmap.pin_all_from("app/javascript/lib", under="utilities", to="lib")
    assert importmap.resolve(str).to_dict()["imports"] == {
        "utilities/example": "lib/example.js"
    }


@pytest.mark.parametrize(
    ("preload", "application", "admin"),
    [
        (True, True, True),
        (False, False, False),
        ("admin", False, True),
        (["application", "admin"], True, True),
        ([], False, False),
    ],
)
def test_preloads_follow_entrypoint_declarations(
    importmap, preload, application, admin
):
    importmap.pin("library", preload=preload)
    resolved = importmap.resolve(str)
    assert bool(resolved.preloads("application")) is application
    assert bool(resolved.preloads("admin")) is admin
    assert "library" in resolved.to_dict()["imports"]


def test_directory_pins_allow_root_asset_paths(importmap, tmp_path):
    root = tmp_path / "app/javascript"
    root.mkdir(parents=True)
    (root / "example.js").write_text("export {};")
    importmap.pin_all_from("app/javascript", under="modules", to="")
    assert importmap.resolve(str).to_dict()["imports"] == {
        "modules/example": "example.js"
    }


def test_preloads_deduplicate_asset_urls(importmap):
    importmap.pin("a", to="shared.js")
    importmap.pin("b", to="shared.js")
    assert len(importmap.resolve(str).preloads()) == 1


def test_integrity_is_opt_in_and_supports_explicit_hashes(importmap, mocker):
    calculate = mocker.Mock(return_value="sha384-YWJj")
    importmap.pin("local")
    importmap.pin("disabled", integrity=False)
    importmap.pin(
        "external", to="https://example.test/module.js", integrity="sha384-ZGVm"
    )
    assert (
        "integrity"
        not in importmap.resolve(str, integrity_resolver=calculate).to_dict()
    )
    calculate.assert_not_called()
    importmap.enable_integrity()
    resolved = importmap.resolve(str, integrity_resolver=calculate).to_dict()
    assert resolved["integrity"] == {
        "local.js": "sha384-YWJj",
        "https://example.test/module.js": "sha384-ZGVm",
    }
    calculate.assert_called_once_with("local.js")


@pytest.mark.parametrize(
    "name", ["", "./module", "../module", "/module", "https:module", "a\\b", "a\nb"]
)
def test_pins_reject_invalid_module_names(importmap, name):
    with pytest.raises(ImportmapError):
        importmap.pin(name)


@pytest.mark.parametrize(
    "target",
    [
        "../private.js",
        ".secret.js",
        "//example.test/a.js",
        "https://user:secret@example.test/a.js",
    ],
)
def test_pins_reject_unsafe_targets(importmap, target):
    with pytest.raises((ImportmapError, AssetError)):
        importmap.pin("module", to=target)


@pytest.mark.parametrize(
    "options",
    [{"preload": 1}, {"preload": [None]}, {"integrity": 1}, {"integrity": "invalid"}],
)
def test_pins_validate_loading_options(importmap, options):
    with pytest.raises(ImportmapError):
        importmap.pin("module", **options)


def test_directory_pins_reject_symlinks_and_outside_paths(importmap, tmp_path):
    with pytest.raises(AssetError):
        importmap.pin_all_from("../outside")
    directory = tmp_path / "app/javascript"
    directory.mkdir(parents=True)
    (directory / "leak.js").symlink_to(tmp_path / "private.js")
    importmap.pin_all_from("app/javascript", under="modules")
    with pytest.raises(AssetError):
        importmap.pins()


def test_configuration_loads_fresh_source_and_removes_deleted_pins(tmp_path):
    path = tmp_path / "config/importmap.py"
    path.parent.mkdir()
    path.write_text('def register(importmap):\n    importmap.pin("old")\n')
    assert ImportMap.load(tmp_path).resolve(str).to_dict()["imports"] == {
        "old": "old.js"
    }
    path.write_text('def register(importmap):\n    importmap.pin("new")\n')
    assert ImportMap.load(tmp_path).resolve(str).to_dict()["imports"] == {
        "new": "new.js"
    }


def test_configuration_requires_an_explicit_registration_callback(tmp_path):
    path = tmp_path / "config/importmap.py"
    path.parent.mkdir()
    path.write_text("pins = {}\n")
    with pytest.raises(ImportmapError, match="register"):
        ImportMap.load(tmp_path)


def test_script_json_round_trips_without_html_script_termination():
    value = {"imports": {"module": "https://example.test/</script><script>&\u2028"}}
    encoded = script_json(value)
    assert "<" not in encoded
    assert "&" not in encoded
    assert json.loads(encoded) == value


def test_digest_tracks_resolved_mapping_changes(importmap):
    importmap.pin("application")
    first = importmap.digest(lambda name: f"/assets/{name}")
    assert importmap.digest(lambda name: f"/assets/{name}") == first
    assert importmap.digest(lambda name: f"/mounted/{name}") != first
