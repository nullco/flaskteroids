import json
from urllib.error import URLError

import pytest

from flaskteroids.assets import AssetError
from flaskteroids.importmaps import ImportMap, ImportmapError
from flaskteroids.importmaps.packages import JSPM_ENDPOINT, HTTPClient, Packager


def project_files(root):
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_pin_delegates_resolution_and_vendors_returned_dependencies(
    importmap_root, package_client
):
    packager = Packager(importmap_root, client=package_client)
    pins = packager.pin("library@1.2.3", preload=False)
    package_client.json.assert_called_once_with(
        JSPM_ENDPOINT,
        body={
            "install": ["library@1.2.3"],
            "flattenScope": True,
            "env": ["browser", "module", "production"],
            "provider": "jspm.io",
        },
    )
    assert {pin.name: pin.version for pin in pins} == {
        "library": "1.2.3",
        "dependency": "2.0.0",
    }
    resolved = ImportMap.load(importmap_root).resolve(str)
    assert resolved.to_dict()["imports"]["library"] == "library.js"
    assert all(pin.name not in {"library", "dependency"} for pin in resolved.preloads())
    source = (importmap_root / "vendor/javascript/library.js").read_text()
    assert "downloaded from https://ga.jspm.io/npm:library@1.2.3/index.js" in source
    assert "export const value = 42" in source
    assert "sourceMappingURL" not in source
    assert {pin.name for pin in packager.packages()} == {"library", "dependency"}


def test_pin_preserves_configuration_and_per_pin_options(
    importmap_root, package_client
):
    path = importmap_root / "config/importmap.py"
    header = '# Application-owned configuration\nSETTING = "preserved"\n\n'
    path.write_text(
        header
        + 'def register(importmap):\n    """Our modules."""\n    importmap.pin(\n        "library",\n        preload=["admin"],\n        integrity=False,\n    ) # important\n    importmap.pin("application")\n'
    )
    Packager(importmap_root, client=package_client).pin("library")
    assert path.read_text().startswith(header)
    assert '"""Our modules."""' in path.read_text()
    assert "# important" in path.read_text()
    Packager(importmap_root, client=package_client).pin("library")
    assert "# important" in path.read_text()
    pin = next(
        pin for pin in ImportMap.load(importmap_root).pins() if pin.name == "library"
    )
    assert pin.preload == ("admin",)
    assert pin.integrity is False


def test_pin_handles_scoped_package_names(importmap_root, package_client):
    package_client.json.return_value = {
        "map": {
            "imports": {
                "@scope/library": "https://ga.jspm.io/npm:@scope/library@1.2.3/index.js"
            }
        }
    }
    result = Packager(importmap_root, client=package_client).pin("@scope/library")
    assert result[0].filename == "@scope--library.js"
    assert (importmap_root / "vendor/javascript/@scope--library.js").is_file()


def test_pristine_requests_recorded_versions(importmap_root, package_client):
    packager = Packager(importmap_root, client=package_client)
    packager.pin("library", preload=False)
    package_client.reset_mock()
    packager.pristine()
    assert package_client.json.call_args.kwargs["body"]["install"] == [
        "library@1.2.3",
        "dependency@2.0.0",
    ]
    assert (
        next(
            pin
            for pin in ImportMap.load(importmap_root).pins()
            if pin.name == "library"
        ).preload
        is False
    )


def test_update_resolves_managed_packages_and_keeps_framework_pins(
    importmap_root, package_client
):
    packager = Packager(importmap_root, client=package_client)
    packager.pin("library", preload=False)
    package_client.reset_mock()
    packager.update(provider="unpkg")
    body = package_client.json.call_args.kwargs["body"]
    assert body["install"] == ["library", "dependency"]
    assert body["provider"] == "unpkg"
    assert (
        ImportMap.load(importmap_root)
        .resolve(str)
        .to_dict()["imports"]["@hotwired/turbo"]
        == "turbo.js"
    )


@pytest.mark.parametrize("command", ["update", "pristine"])
def test_package_maintenance_without_managed_pins_is_offline(
    importmap_root, package_client, command
):
    assert getattr(Packager(importmap_root, client=package_client), command)() == ()
    package_client.json.assert_not_called()


def test_unpin_removes_only_named_pins_and_keeps_transitive_dependencies(
    importmap_root, package_client
):
    packager = Packager(importmap_root, client=package_client)
    packager.pin("library")
    package_client.reset_mock()
    assert packager.unpin("library", "missing") == ("library",)
    assert not (importmap_root / "vendor/javascript/library.js").exists()
    assert (importmap_root / "vendor/javascript/dependency.js").is_file()
    assert (
        "library"
        not in ImportMap.load(importmap_root).resolve(str).to_dict()["imports"]
    )
    package_client.json.assert_not_called()


def test_unpin_retains_files_used_by_manual_aliases(importmap_root, package_client):
    packager = Packager(importmap_root, client=package_client)
    packager.pin("library")
    path = importmap_root / "config/importmap.py"
    path.write_text(path.read_text() + '    importmap.pin("alias", to="library.js")\n')
    packager.unpin("library")
    assert (importmap_root / "vendor/javascript/library.js").is_file()
    assert (
        ImportMap.load(importmap_root).resolve(str).to_dict()["imports"]["alias"]
        == "library.js"
    )


def test_unpin_last_declaration_leaves_valid_configuration(
    importmap_root, package_client
):
    path = importmap_root / "config/importmap.py"
    path.write_text('def register(importmap):\n    importmap.pin("application")\n')
    Packager(importmap_root, client=package_client).unpin("application")
    assert ImportMap.load(importmap_root).pins() == ()


@pytest.mark.parametrize(
    "mapping",
    [
        {},
        {"map": {}},
        {"map": {"imports": {}}},
        {
            "map": {
                "imports": {"library": "https://example.test/lib.js"},
                "scopes": {"/": {"a": "/b.js"}},
            }
        },
        {"map": {"imports": {"library": "http://example.test/library.js"}}},
        {"map": {"imports": {"../unsafe": "https://example.test/library.js"}}},
        {
            "map": {
                "imports": {
                    "a/b": "https://example.test/a.js",
                    "a--b": "https://example.test/b.js",
                }
            }
        },
    ],
)
def test_invalid_resolution_preserves_application_files(
    importmap_root, package_client, mapping
):
    before = project_files(importmap_root)
    package_client.json.return_value = mapping
    with pytest.raises((ImportmapError, AssetError)):
        Packager(importmap_root, client=package_client).pin("library")
    assert project_files(importmap_root) == before


def test_download_failure_preserves_all_existing_files(importmap_root, package_client):
    packager = Packager(importmap_root, client=package_client)
    packager.pin("library")
    before = project_files(importmap_root)
    package_client.request.side_effect = [
        b"new code",
        ImportmapError("connection failed"),
    ]
    with pytest.raises(ImportmapError, match="connection failed"):
        packager.pin("library")
    assert project_files(importmap_root) == before


def test_pin_rejects_collisions_with_other_managed_packages(
    importmap_root, package_client
):
    packager = Packager(importmap_root, client=package_client)
    package_client.json.return_value = {
        "map": {"imports": {"a--b": "https://example.test/a@1.0.0.js"}}
    }
    packager.pin("a--b")
    before = project_files(importmap_root)
    package_client.json.return_value = {
        "map": {"imports": {"a/b": "https://example.test/b@1.0.0.js"}}
    }
    with pytest.raises(ImportmapError, match="colliding"):
        packager.pin("a/b")
    assert project_files(importmap_root) == before


def test_pin_preserves_framework_asset_pins_on_filename_collision(
    importmap_root, package_client
):
    package_client.json.return_value = {
        "map": {"imports": {"turbo": "https://example.test/turbo@1.0.0.js"}}
    }
    before = project_files(importmap_root)
    with pytest.raises(ImportmapError, match="colliding"):
        Packager(importmap_root, client=package_client).pin("turbo")
    assert project_files(importmap_root) == before


@pytest.mark.parametrize("source", ["app/javascript", "app/assets"])
def test_pin_rejects_downloads_that_duplicate_application_assets(
    importmap_root, package_client, source
):
    local = importmap_root / source / "library.js"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text("export const local = true;")
    before = project_files(importmap_root)
    with pytest.raises(ImportmapError, match="conflicts"):
        Packager(importmap_root, client=package_client).pin("library")
    assert project_files(importmap_root) == before


def test_pin_keeps_configuration_permissions_and_publishes_readable_assets(
    importmap_root, package_client
):
    path = importmap_root / "config/importmap.py"
    path.chmod(0o640)
    Packager(importmap_root, client=package_client).pin("library")
    assert path.stat().st_mode & 0o777 == 0o640
    assert (
        importmap_root / "vendor/javascript/library.js"
    ).stat().st_mode & 0o777 == 0o644


def test_pin_rejects_symlinked_vendor_directory(
    importmap_root, package_client, tmp_path
):
    (importmap_root / "vendor/javascript/.keep").unlink()
    (importmap_root / "vendor/javascript").rmdir()
    (importmap_root / "vendor/javascript").symlink_to(tmp_path.parent)
    with pytest.raises(AssetError):
        Packager(importmap_root, client=package_client).pin("library")


@pytest.mark.parametrize(
    "url",
    [
        "http://example.test/file.js",
        "file:///etc/passwd",
        "https://user:secret@example.test/file.js",
    ],
)
def test_http_client_rejects_unsafe_download_urls(url, mocker):
    opener = mocker.patch("flaskteroids.importmaps.packages.build_opener")
    with pytest.raises(ImportmapError):
        HTTPClient().request(url)
    opener.assert_not_called()


def test_http_client_posts_json_with_a_timeout(mocker):
    response = mocker.MagicMock()
    response.url = JSPM_ENDPOINT
    response.read.return_value = b'{"map": {"imports": {}}}'
    opener = mocker.patch("flaskteroids.importmaps.packages.build_opener").return_value
    opener.open.return_value.__enter__.return_value = response
    assert HTTPClient().json(JSPM_ENDPOINT, body={"install": ["library"]}) == {
        "map": {"imports": {}}
    }
    request = opener.open.call_args.args[0]
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {"install": ["library"]}
    assert opener.open.call_args.kwargs["timeout"] == 30


def test_http_client_preserves_transport_failure_diagnostics(mocker):
    opener = mocker.patch("flaskteroids.importmaps.packages.build_opener").return_value
    opener.open.side_effect = URLError("network unavailable")
    with pytest.raises(ImportmapError, match="network unavailable"):
        HTTPClient().json(JSPM_ENDPOINT)


@pytest.mark.parametrize("data", [b"not json", b"[]"])
def test_http_client_rejects_invalid_json_responses(mocker, data):
    mocker.patch.object(HTTPClient, "request", return_value=data)
    with pytest.raises(ImportmapError):
        HTTPClient().json(JSPM_ENDPOINT)


def test_http_client_bounds_response_size(mocker):
    mocker.patch("flaskteroids.importmaps.packages.MAX_DOWNLOAD_BYTES", 8)
    response = mocker.MagicMock()
    response.url = JSPM_ENDPOINT
    response.read.return_value = b"123456789"
    opener = mocker.patch("flaskteroids.importmaps.packages.build_opener").return_value
    opener.open.return_value.__enter__.return_value = response
    with pytest.raises(ImportmapError, match="exceeds"):
        HTTPClient().request(JSPM_ENDPOINT)
