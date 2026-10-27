import hashlib
import json
import posixpath
import re
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from flask import abort, current_app, request, url_for
from markupsafe import Markup
from werkzeug.security import safe_join

from flaskteroids._assets.css import rewrite_urls
from flaskteroids._html import attributes

SOURCE_PATH = "app/assets"
OUTPUT_PATH = "public/assets"
MANIFEST_NAME = ".manifest.json"


class AssetError(ValueError):
    pass


def _logical_name(name):
    if (
        not isinstance(name, str)
        or not name
        or "\\" in name
        or any(ord(char) < 32 or ord(char) == 127 for char in name)
        or any(part.startswith(".") or not part for part in name.split("/"))
    ):
        raise AssetError(f"Invalid asset name: {name!r}")
    return name


def _safe_path(directory, name):
    joined = safe_join(str(directory), name)
    if joined is None:
        raise AssetError(f"Asset path escapes its directory: {name!r}")
    path = directory
    for part in Path(joined).relative_to(directory).parts:
        path = path / part
        if path.is_symlink():
            raise AssetError(f"Asset symlinks are not supported: {path}")
    return path


def _logical_match(name, names):
    _logical_name(name)
    if name in names:
        return name
    matches = [path for path in names if path.partition("/")[2] == name]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise AssetError(
            f"Ambiguous asset name: {name}; use its directory-qualified name"
        )
    raise AssetError(f"Asset not found: {name}")


class AssetPipeline:
    def __init__(self, root, *, source_path=SOURCE_PATH, output_path=OUTPUT_PATH):
        self.root = Path(root).resolve()
        self.source = self._directory(source_path)
        self.output = self._directory(output_path)
        if self.output.is_relative_to(self.source) or self.source.is_relative_to(
            self.output
        ):
            raise AssetError("Asset source and output directories must not overlap")

    def _directory(self, name):
        path = self.root / name
        if not path.is_relative_to(self.root):
            raise AssetError("Asset directories must be inside the application root")
        path = _safe_path(self.root, path.relative_to(self.root).as_posix())
        if path.resolve() == self.root or (path.exists() and not path.is_dir()):
            raise AssetError(f"Invalid asset directory: {path}")
        return path

    def source_files(self):
        self._directory(self.source)
        files = {}
        for path in sorted(self.source.rglob("*")):
            name = path.relative_to(self.source).as_posix()
            if any(part.startswith(".") for part in name.split("/")):
                continue
            _logical_name(name)
            path = _safe_path(self.source, name)
            if path.is_file():
                files[name] = path
        return files

    def source_name(self, name):
        self._directory(self.source)
        _logical_name(name)
        if _safe_path(self.source, name).is_file():
            return name
        candidates = []
        if self.source.is_dir():
            candidates += [
                f"{path.name}/{name}"
                for path in self.source.iterdir()
                if path.is_dir() and not path.name.startswith(".")
            ]
        names = [path for path in candidates if _safe_path(self.source, path).is_file()]
        return _logical_match(name, names)

    def manifest(self):
        self._directory(self.output)
        path = _safe_path(self.output, MANIFEST_NAME)
        try:
            manifest = json.loads(path.read_text())
        except (OSError, ValueError) as error:
            raise AssetError(
                "Asset manifest is missing or invalid. Run bin/flask assets:precompile."
            ) from error
        if not isinstance(manifest, dict):
            raise AssetError(
                "Asset manifest must map logical names to fingerprinted files"
            )
        for name, compiled in manifest.items():
            _logical_name(name)
            _logical_name(compiled)
            path = PurePosixPath(name)
            pattern = (
                re.escape(str(path.with_suffix("")))
                + r"-[0-9a-f]{64}"
                + re.escape(path.suffix)
            )
            if not re.fullmatch(pattern, compiled):
                raise AssetError(f"Invalid fingerprinted asset in manifest: {name}")
        return manifest

    def compiled_name(self, name):
        manifest = self.manifest()
        compiled = manifest[_logical_match(name, manifest)]
        if not _safe_path(self.output, compiled).is_file():
            raise AssetError(f"Compiled asset not found: {name}. Recompile assets.")
        return compiled

    def precompile(self):
        contents = {
            name: path.read_bytes() for name, path in self.source_files().items()
        }
        manifest, compiled_contents, visiting = {}, {}, []

        def compile_asset(name):
            _logical_name(name)
            if name in manifest:
                return manifest[name]
            if name in visiting:
                raise AssetError(
                    f"Circular CSS asset dependency: {' -> '.join([*visiting, name])}"
                )
            if name not in contents:
                raise AssetError(f"CSS asset not found: {name}")
            visiting.append(name)

            def resolve(reference):
                url = urlsplit(reference)
                if url.scheme or url.netloc or not url.path or url.path.startswith("/"):
                    return reference
                target = posixpath.normpath(
                    posixpath.join(posixpath.dirname(name), unquote(url.path))
                )
                relative = posixpath.relpath(
                    compile_asset(target), posixpath.dirname(name) or "."
                )
                return urlunsplit(
                    ("", "", quote(relative, safe="/"), url.query, url.fragment)
                )

            data = contents[name]
            if name.lower().endswith(".css"):
                try:
                    data = rewrite_urls(data, resolve)
                except ValueError as error:
                    raise AssetError(f"Cannot compile CSS {name}: {error}") from error
            visiting.pop()
            path = PurePosixPath(name)
            manifest[name] = str(
                path.with_name(
                    f"{path.stem}-{hashlib.sha256(data).hexdigest()}{path.suffix}"
                )
            )
            compiled_contents[name] = data
            return manifest[name]

        for name in sorted(contents):
            compile_asset(name)
        self._directory(self.output)
        self.output.mkdir(parents=True, exist_ok=True)
        for name, data in compiled_contents.items():
            path = _safe_path(self.output, manifest[name])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        target = _safe_path(self.output, MANIFEST_NAME)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=self.output, prefix=".manifest-", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            try:
                temporary.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
                temporary.flush()
                temporary_path.replace(target)
            finally:
                temporary_path.unlink(missing_ok=True)
        return manifest


def init_assets(app):
    config = app.config.assets
    pipeline = AssetPipeline(
        app.project_root, source_path=config.source_path, output_path=config.output_path
    )
    app.extensions["flaskteroids.assets"] = pipeline
    app.static_folder = (
        pipeline.source if app.env.development or app.env.test else pipeline.output
    )
    prefix = config.prefix
    if (
        not isinstance(prefix, str)
        or not prefix.startswith("/")
        or any(char in prefix for char in "?#%")
    ):
        raise AssetError(
            "Asset URL prefix must be an absolute path without query strings"
        )
    _logical_name(prefix.rstrip("/")[1:])
    app.static_url_path = prefix
    app.add_url_rule(
        f"{app.static_url_path}/<path:filename>",
        endpoint="static",
        view_func=app.send_static_file,
        build_only=not config.serve,
    )
    app.jinja_env.globals.update(
        asset_path=asset_path, stylesheet_link_tag=stylesheet_link_tag
    )

    @app.url_value_preprocessor
    def validate_asset_path(endpoint, values):
        if endpoint == "static":
            try:
                filename = _logical_name(values["filename"])
                folder = Path(app.static_folder).relative_to(app.project_root)
                _safe_path(app.project_root, (folder / filename).as_posix())
            except ValueError, OSError:
                abort(404)

    @app.after_request
    def asset_headers(response):
        if request.endpoint == "static" and response.status_code in (200, 206, 304):
            response.headers["X-Content-Type-Options"] = "nosniff"
            if (
                not (app.env.development or app.env.test)
                and (response.cache_control.max_age or 0) > 0
            ):
                response.cache_control.immutable = True
        return response


def asset_path(name):
    pipeline = current_app.extensions["flaskteroids.assets"]
    filename = (
        pipeline.source_name(name)
        if current_app.env.development or current_app.env.test
        else pipeline.compiled_name(name)
    )
    return url_for("static", filename=filename)


def stylesheet_link_tag(*names, **kwargs):
    if "href" in kwargs or "rel" in kwargs:
        raise ValueError("Stylesheet href and rel are set by stylesheet_link_tag")
    tags = []
    for name in names:
        _logical_name(name)
        source = name if name.endswith(".css") else name + ".css"
        tags.append(
            f"<link {attributes({'rel': 'stylesheet', 'href': asset_path(source), **kwargs})}>"
        )
    return Markup("\n".join(tags))
