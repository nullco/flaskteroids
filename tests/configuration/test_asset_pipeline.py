import hashlib
import json
from urllib.parse import quote, urljoin

import pytest
from click.testing import CliRunner
from flask import url_for
from flask.cli import cli
from markupsafe import Markup

from flaskteroids.assets import AssetError
from flaskteroids.helpers import asset_path, stylesheet_link_tag
from tests.assertions import HTML


def compile_assets(root, *args):
    result = CliRunner().invoke(cli, ["assets:precompile", "--root", str(root), *args])
    assert result.exit_code == 0, result.output
    return json.loads((root / "public/assets/.manifest.json").read_text())


@pytest.mark.parametrize("environment", ["development", "test"])
def test_sources_use_flasks_static_endpoint(asset_application, environment):
    app = asset_application(environment)
    with app.test_request_context():
        assert asset_path("application.css") == "/assets/stylesheets/application.css"
        assert asset_path("logo.png") == "/assets/images/logo.png"
        assert HTML(stylesheet_link_tag("application")).has(
            "link", rel="stylesheet", href=asset_path("application.css")
        )
    assert app.static_folder.endswith("/app/assets")
    assert app.static_url_path == "/assets"
    with app.test_request_context():
        assert url_for("static", filename="images/logo.png") == asset_path("logo.png")
    client = app.test_client()
    response = client.get("/assets/stylesheets/application.css")
    assert response.data == b"body { color: red; }"
    assert response.mimetype == "text/css"
    assert "no-cache" in response.headers["Cache-Control"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert client.get("/assets/images/logo.png").data == b"image bytes"
    partial = client.get("/assets/images/logo.png", headers={"Range": "bytes=0-4"})
    assert partial.status_code == 206
    assert partial.data == b"image"
    assert partial.headers["Content-Range"] == "bytes 0-4/11"
    assert client.get("/static/anything.css").status_code == 404
    assert client.head("/assets/stylesheets/application.css").data == b""


def test_development_sees_edits_without_precompilation(asset_application, asset_root):
    app = asset_application()
    client = app.test_client()
    first = client.get("/assets/stylesheets/application.css")
    (asset_root / "app/assets/stylesheets/application.css").write_text(
        "body { color: blue; }"
    )
    response = client.get(
        "/assets/stylesheets/application.css",
        headers={"If-None-Match": first.headers["ETag"]},
    )
    assert response.status_code == 200
    assert response.data == b"body { color: blue; }"
    assert not (asset_root / "public/assets").exists()
    assert (
        client.get(
            "/assets/stylesheets/application.css",
            headers={"If-None-Match": response.headers["ETag"]},
        ).status_code
        == 304
    )


def test_helpers_escape_attributes_and_return_trusted_markup(
    asset_application, asset_root
):
    (asset_root / 'app/assets/stylesheets/a"&.css').write_text("body {}")
    app = asset_application()
    with app.test_request_context():
        tag = stylesheet_link_tag(
            'a"&.css',
            media=Markup('screen" onclick="evil'),
            **{"data-turbo-track": "reload"},
        )
        assert isinstance(tag, Markup)
        assert HTML(tag).has(
            "link",
            href=asset_path('a"&.css'),
            media='screen" onclick="evil',
            **{"data-turbo-track": "reload"},
        )
        with pytest.raises(ValueError):
            stylesheet_link_tag("application", **{'bad"name': "value"})
        with pytest.raises(ValueError):
            stylesheet_link_tag("application", href="javascript:evil")


@pytest.mark.parametrize(
    "name",
    [
        "../secret",
        "/secret",
        "a/../secret",
        "a//b.css",
        "a\\b.css",
        ".keep",
        "bad\x00.css",
    ],
)
def test_unsafe_helper_names_are_rejected(asset_application, name):
    app = asset_application()
    with app.test_request_context(), pytest.raises(AssetError):
        asset_path(name)


@pytest.mark.parametrize(
    "name",
    [
        "missing.css",
        ".keep",
        ".manifest.json",
        "../private.txt",
        "%2e%2e/private.txt",
        "app/assets/images/logo.png",
    ],
)
def test_static_requests_reject_missing_hidden_and_project_files(
    asset_application, name
):
    assert asset_application().test_client().get(f"/assets/{name}").status_code == 404


def test_precompilation_is_deterministic_and_content_fingerprinted(
    asset_root, monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path.parent)
    first = compile_assets(asset_root)
    manifest_bytes = (asset_root / "public/assets/.manifest.json").read_bytes()
    assert {"stylesheets/application.css", "images/logo.png"} <= first.keys()
    digest = hashlib.sha256(b"body { color: red; }").hexdigest()
    assert (
        first["stylesheets/application.css"] == f"stylesheets/application-{digest}.css"
    )
    assert (
        asset_root / "public/assets" / first["images/logo.png"]
    ).read_bytes() == b"image bytes"
    assert compile_assets(asset_root) == first
    assert (asset_root / "public/assets/.manifest.json").read_bytes() == manifest_bytes
    (asset_root / "app/assets/stylesheets/application.css").write_text("updated")
    assert (
        compile_assets(asset_root)["stylesheets/application.css"]
        != first["stylesheets/application.css"]
    )


def test_production_static_endpoint_serves_the_output_directory(
    asset_application, asset_root
):
    manifest = compile_assets(asset_root)
    app = asset_application("production")
    with app.test_request_context():
        url = asset_path("application.css")
        assert url == f"/assets/{manifest['stylesheets/application.css']}"
    client = app.test_client()
    response = client.get(url)
    assert response.status_code == 200
    assert response.data == b"body { color: red; }"
    assert response.mimetype == "text/css"
    assert "public" in response.headers["Cache-Control"]
    assert "max-age=31536000" in response.headers["Cache-Control"]
    assert "immutable" in response.headers["Cache-Control"]
    assert (
        client.get(url, headers={"If-None-Match": response.headers["ETag"]}).status_code
        == 304
    )
    assert client.get("/assets/stylesheets/application.css").status_code == 404
    assert client.get("/assets/.manifest.json").status_code == 404
    (asset_root / "public/assets/extra.txt").write_text("public file")
    assert client.get("/assets/extra.txt").data == b"public file"
    assert client.get("/static/anything.css").status_code == 404


@pytest.mark.parametrize(
    "problem",
    [
        "missing",
        "invalid",
        "missing_entry",
        "missing_file",
        "unsafe",
        "wrong_fingerprint",
    ],
)
def test_production_manifest_errors_raise_asset_errors(
    asset_application, asset_root, problem
):
    manifest = compile_assets(asset_root)
    path = asset_root / "public/assets/.manifest.json"
    if problem == "missing":
        path.unlink()
    elif problem == "invalid":
        path.write_text("not JSON")
    elif problem == "missing_entry":
        path.write_text("{}")
    elif problem == "missing_file":
        (
            asset_root / "public/assets" / manifest["stylesheets/application.css"]
        ).unlink()
    else:
        manifest["stylesheets/application.css"] = (
            "../secret" if problem == "unsafe" else "logo.png"
        )
        path.write_text(json.dumps(manifest))
    app = asset_application("production")
    with app.test_request_context(), pytest.raises(AssetError):
        asset_path("application.css")
    assert (
        app.test_client().get("/assets/stylesheets/application.css").status_code == 404
    )


@pytest.mark.parametrize(
    "location",
    [
        "source_file",
        "source_directory",
        "output_directory",
        "compiled_file",
        "manifest",
    ],
)
def test_static_requests_reject_asset_symlinks(
    asset_application, asset_root, tmp_path, location
):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "secret.css").write_text("secret")
    manifest = compile_assets(asset_root)
    if location == "source_file":
        (asset_root / "app/assets/stylesheets/leak.css").symlink_to(
            outside / "secret.css"
        )
    elif location == "source_directory":
        (asset_root / "app/assets/stylesheets/leak").symlink_to(
            outside, target_is_directory=True
        )
    elif location == "output_directory":
        (asset_root / "public/assets").rename(asset_root / "public/old-assets")
        (asset_root / "public/assets").symlink_to(outside, target_is_directory=True)
        with pytest.raises(AssetError):
            asset_application()
        return
    else:
        name = (
            manifest["stylesheets/application.css"]
            if location == "compiled_file"
            else ".manifest.json"
        )
        path = asset_root / "public/assets" / name
        path.unlink()
        path.symlink_to(outside / "secret.css")
    production = location in ("compiled_file", "manifest")
    app = asset_application("production" if production else "development")
    logical_name = (
        "application.css"
        if production
        else ("leak/secret.css" if location == "source_directory" else "leak.css")
    )
    with app.test_request_context(), pytest.raises(AssetError):
        asset_path(logical_name)
    assert (
        app.test_client()
        .get(
            f"/assets/{manifest['stylesheets/application.css']}"
            if location == "compiled_file"
            else (
                "/assets/.manifest.json"
                if location == "manifest"
                else f"/assets/stylesheets/{logical_name}"
            )
        )
        .status_code
        == 404
    )
    result = CliRunner().invoke(cli, ["assets:precompile", "--root", str(asset_root)])
    assert result.exit_code != 0


def test_ambiguous_short_names_require_directory_qualification(
    asset_root, asset_application
):
    (asset_root / "app/assets/images/application.css").write_text("duplicate")
    compile_assets(asset_root)
    for environment in ("development", "production"):
        app = asset_application(environment)
        with app.test_request_context():
            with pytest.raises(AssetError, match="Ambiguous"):
                asset_path("application.css")
            url = asset_path("stylesheets/application.css")
        assert app.test_client().get(url).data == b"body { color: red; }"


def test_prefix_and_reverse_proxy_serving_are_configurable(
    asset_root, asset_application
):
    manifest = compile_assets(asset_root)
    app = asset_application("production", prefix="/custom/assets", serve=False)
    with app.test_request_context(environ_overrides={"SCRIPT_NAME": "/mounted"}):
        assert (
            asset_path("application.css")
            == f"/mounted/custom/assets/{manifest['stylesheets/application.css']}"
        )
    assert (
        app.test_client()
        .get(f"/custom/assets/{manifest['stylesheets/application.css']}")
        .status_code
        == 404
    )


@pytest.mark.parametrize(
    "option, value",
    [
        ("output_path", "../outside"),
        ("source_path", "../outside"),
        ("output_path", "app/assets"),
        ("prefix", "//assets"),
        ("prefix", "/assets?x=1"),
        ("source_path", "."),
        ("prefix", "/"),
    ],
)
def test_invalid_configuration_fails_during_setup(asset_application, option, value):
    with pytest.raises(AssetError):
        asset_application(**{option: value})


@pytest.mark.parametrize(
    "reference",
    [
        "url(../images/logo.png)",
        "url('../images/logo.png')",
        'URL( "../images/logo.png" )',
        r'url("../images/l\6f go.png")',
        "url(../images/./logo.png)",
        "url(../images/l%6Fgo.png)",
    ],
)
def test_css_urls_resolve_to_fingerprinted_images(
    asset_root, asset_application, reference
):
    source = f"body {{ background: {reference}; }}"
    (asset_root / "app/assets/stylesheets/application.css").write_text(source)
    manifest = compile_assets(asset_root)
    css = (
        asset_root / "public/assets" / manifest["stylesheets/application.css"]
    ).read_text()
    assert manifest["images/logo.png"] in css
    app = asset_application("production", prefix="/custom/assets")
    with app.test_request_context():
        css_url = asset_path("application.css")
    client = app.test_client()
    assert client.get(css_url).data == css.encode()
    image_url = urljoin(css_url, f"../{manifest['images/logo.png']}")
    assert client.get(image_url).data == b"image bytes"
    assert (
        asset_application()
        .test_client()
        .get("/assets/stylesheets/application.css")
        .text
        == source
    )


def test_css_imports_and_fonts_resolve_relative_to_stylesheet(
    asset_root, asset_application
):
    stylesheets = asset_root / "app/assets/stylesheets"
    (stylesheets / "themes").mkdir()
    (stylesheets / "application.css").write_text('@import "themes/theme.css";')
    (stylesheets / "base.css").write_text("body { color: red; }")
    (stylesheets / "themes/theme.css").write_text(
        '@import/* theme */url("../base.css"); '
        '.logo { background: url("../../images/logo.png?v=1#icon"); } '
        '@font-face { font-family: Demo; src: url("../../fonts/demo.woff2"); }'
    )
    fonts = asset_root / "app/assets/fonts"
    fonts.mkdir()
    (fonts / "demo.woff2").write_bytes(b"font bytes")
    manifest = compile_assets(asset_root)
    output = asset_root / "public/assets"
    assert (
        manifest["stylesheets/themes/theme.css"].removeprefix("stylesheets/")
        in (output / manifest["stylesheets/application.css"]).read_text()
    )
    theme = (output / manifest["stylesheets/themes/theme.css"]).read_text()
    assert (
        f"../{manifest['stylesheets/base.css'].removeprefix('stylesheets/')}" in theme
    )
    assert f"../../{manifest['images/logo.png']}?v=1#icon" in theme
    assert f"../../{manifest['fonts/demo.woff2']}" in theme
    app = asset_application("production")
    with app.test_request_context():
        theme_url = asset_path("themes/theme.css")
    assert (
        app.test_client()
        .get(urljoin(theme_url, f"../../{manifest['fonts/demo.woff2']}"))
        .data
        == b"font bytes"
    )
    (asset_root / "app/assets/images/logo.png").write_bytes(b"new image")
    changed = compile_assets(asset_root)
    for name in (
        "images/logo.png",
        "stylesheets/themes/theme.css",
        "stylesheets/application.css",
    ):
        assert changed[name] != manifest[name]
    assert changed["stylesheets/base.css"] == manifest["stylesheets/base.css"]
    assert compile_assets(asset_root) == changed


@pytest.mark.parametrize(
    "name, reference",
    [
        ("a b.png", r'url("../images/a\ b.png")'),
        ("a(b).png", r"url(../images/a\(b\).png)"),
        ('a"b.png', r'url("../images/a\"b.png")'),
    ],
)
def test_css_escaped_filenames_are_safely_encoded(asset_root, name, reference):
    (asset_root / "app/assets/images" / name).write_bytes(b"image")
    (asset_root / "app/assets/stylesheets/application.css").write_text(
        f"a {{ background: {reference} }}"
    )
    manifest = compile_assets(asset_root)
    css = (
        asset_root / "public/assets" / manifest["stylesheets/application.css"]
    ).read_text()
    assert quote(manifest[f"images/{name}"], safe="/") in css


def test_css_external_urls_comments_and_strings_are_unchanged(asset_root):
    css = """/* url(missing.png) @import "missing.css"; */
.a { content: "url(missing.png)"; }
.b { background: url(data:image/svg+xml;base64,PHN2Zz4=); }
.c { background: url(https://example.test/image.png); }
.d { background: url(//example.test/image.png); }
.e { background: url(/static/image.png); }
.f { filter: url(#filter); }
.g { background: url(); }
@import "https://example.test/theme.css";
"""
    (asset_root / "app/assets/stylesheets/application.css").write_text(css)
    manifest = compile_assets(asset_root)
    assert (
        asset_root / "public/assets" / manifest["stylesheets/application.css"]
    ).read_text() == css


@pytest.mark.parametrize(
    "css, error",
    [
        ("a { background: url(missing.png) }", "CSS asset not found"),
        ('@import "application.css";', "Circular CSS asset dependency"),
        ("@import url(application.css);", "Circular CSS asset dependency"),
        ("a { background: url(../../secret.png) }", "Invalid asset name"),
    ],
)
def test_css_errors_preserve_previous_good_build(asset_root, css, error):
    compile_assets(asset_root)
    manifest = asset_root / "public/assets/.manifest.json"
    previous = manifest.read_bytes()
    (asset_root / "app/assets/stylesheets/application.css").write_text(css)
    result = CliRunner().invoke(cli, ["assets:precompile", "--root", str(asset_root)])
    assert result.exit_code != 0
    assert error in result.output
    assert manifest.read_bytes() == previous


def test_stylesheet_helper_supports_multiple_names(asset_root, asset_application):
    (asset_root / "app/assets/stylesheets/print.css").write_text("a {}")
    with asset_application().test_request_context():
        tags = stylesheet_link_tag("application", "print.css", media="all")
        assert tags.count('<link rel="stylesheet"') == 2
        assert 'href="/assets/stylesheets/print.css"' in tags


def test_custom_compilation_paths_match_runtime_configuration(
    asset_root, asset_application
):
    result = CliRunner().invoke(
        cli,
        [
            "assets:precompile",
            "--root",
            str(asset_root),
            "--source",
            "app/assets",
            "--output",
            "public/custom-assets",
        ],
    )
    assert result.exit_code == 0, result.output
    app = asset_application("production", output_path="public/custom-assets")
    with app.test_request_context():
        url = asset_path("application.css")
    assert app.test_client().get(url).status_code == 200


@pytest.mark.parametrize("environment", ["development", "production"])
def test_native_static_directory_and_url_are_customizable(
    asset_root, asset_application, environment
):
    (asset_root / "app/assets").rename(asset_root / "frontend")
    result = CliRunner().invoke(
        cli,
        [
            "assets:precompile",
            "--root",
            str(asset_root),
            "--source",
            "frontend",
            "--output",
            "static",
        ],
    )
    assert result.exit_code == 0, result.output
    app = asset_application(
        environment,
        source_path="frontend",
        output_path="static",
        prefix="/custom/assets/",
    )
    assert app.static_folder == str(
        asset_root / ("frontend" if environment == "development" else "static")
    )
    assert app.static_url_path == "/custom/assets"
    with app.test_request_context(environ_overrides={"SCRIPT_NAME": "/mounted"}):
        assert asset_path("logo.png").startswith("/mounted/custom/assets/images/logo")
    with app.test_request_context():
        url = asset_path("application.css")
    assert app.test_client().get(url).data == b"body { color: red; }"
    assert (
        app.test_client().get("/assets/stylesheets/application.css").status_code == 404
    )


@pytest.mark.parametrize("environment", ["development", "production"])
@pytest.mark.parametrize("max_age", [None, 0, 60])
def test_native_flask_cache_configuration_is_respected(
    asset_root, asset_application, environment, max_age
):
    compile_assets(asset_root)
    app = asset_application(
        environment, flask_config={"SEND_FILE_MAX_AGE_DEFAULT": max_age}
    )
    with app.test_request_context():
        url = asset_path("application.css")
    response = app.test_client().get(url)
    assert response.cache_control.max_age == max_age
    assert response.cache_control.immutable == (
        environment == "production" and bool(max_age)
    )
    assert bool(response.cache_control.no_cache) == (not max_age)


def test_static_serving_preserves_published_assets_across_manifest_changes(
    asset_root, asset_application
):
    compile_assets(asset_root)
    app = asset_application("production")
    with app.test_request_context():
        old_url = asset_path("application.css")
    (asset_root / "app/assets/stylesheets/application.css").write_text("changed")
    compile_assets(asset_root)
    assert app.test_client().get(old_url).data == b"body { color: red; }"
    (asset_root / "public/assets/.manifest.json").unlink()
    assert app.test_client().get(old_url).status_code == 200
    with app.test_request_context(), pytest.raises(AssetError, match="manifest"):
        asset_path("application.css")


@pytest.mark.parametrize("environment", ["development", "production"])
def test_static_serving_rejects_root_symlink_replacement_after_boot(
    asset_root, asset_application, tmp_path, environment
):
    compile_assets(asset_root)
    app = asset_application(environment)
    with app.test_request_context():
        url = asset_path("application.css")
    folder = asset_root / (
        "app/assets" if environment == "development" else "public/assets"
    )
    folder.rename(asset_root / "previous-assets")
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    folder.symlink_to(outside, target_is_directory=True)
    assert app.test_client().get(url).status_code == 404
