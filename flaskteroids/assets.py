import base64
import hashlib
import json
import posixpath
import re
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from flask import abort, current_app, request, send_from_directory, url_for
from markupsafe import Markup

from flaskteroids._assets.css import rewrite_urls
from flaskteroids._assets.packages import packaged_assets
from flaskteroids._assets.paths import AssetError as AssetError
from flaskteroids._assets.paths import directory_path, url_prefix
from flaskteroids._assets.paths import logical_name as _logical_name
from flaskteroids._assets.paths import safe_path as _safe_path
from flaskteroids._html import attributes

SOURCE_PATH = "app/assets"
OUTPUT_PATH = "public/assets"
MANIFEST_NAME = ".manifest.json"
JAVASCRIPT_PATHS = ("app/javascript", "vendor/javascript")


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
        self.sources = tuple(
            dict.fromkeys(
                (self.source, *(self._directory(p) for p in JAVASCRIPT_PATHS))
            )
        )
        for source in self.sources:
            if self.output.is_relative_to(source) or source.is_relative_to(self.output):
                raise AssetError("Asset source and output directories must not overlap")
        for index, source in enumerate(self.sources):
            if any(
                source.is_relative_to(other) or other.is_relative_to(source)
                for other in self.sources[index + 1 :]
            ):
                raise AssetError("Asset source directories must not overlap")

    def _directory(self, name):
        return directory_path(self.root, name)

    def source_files(self):
        files = {}
        for directory in self.sources:
            self._directory(directory)
            for path in sorted(directory.rglob("*")):
                name = path.relative_to(directory).as_posix()
                if any(part.startswith(".") for part in name.split("/")):
                    continue
                _logical_name(name)
                path = _safe_path(directory, name)
                if path.is_file():
                    if name in files:
                        raise AssetError(f"Duplicate asset name: {name}")
                    files[name] = path
        for name, path in packaged_assets().items():
            files.setdefault(name, path)
        return files

    def source_file(self, name):
        _logical_name(name)
        matches = []
        for directory in self.sources:
            self._directory(directory)
            path = _safe_path(directory, name)
            if path.is_file():
                matches.append(path)
        if len(matches) > 1:
            raise AssetError(f"Duplicate asset name: {name}")
        if matches:
            return matches[0]
        packaged = packaged_assets().get(name)
        if packaged is None or not packaged.is_file():
            raise AssetError(f"Asset not found: {name}")
        return packaged

    def source_name(self, name):
        _logical_name(name)
        names = set(packaged_assets())
        for directory in self.sources:
            self._directory(directory)
            if _safe_path(directory, name).is_file():
                names.add(name)
            if directory.is_dir():
                for path in directory.iterdir():
                    if path.is_dir() and not path.name.startswith("."):
                        candidate = f"{path.name}/{name}"
                        if _safe_path(directory, candidate).is_file():
                            names.add(candidate)
        logical = _logical_match(name, names)
        self.source_file(logical)
        return logical

    def asset_bytes(self, name, *, compiled=False):
        if compiled:
            return _safe_path(self.output, self.compiled_name(name)).read_bytes()
        return self.source_file(self.source_name(name)).read_bytes()

    def asset_integrity(self, name, *, compiled=False):
        data = self.asset_bytes(name, compiled=compiled)
        digest = base64.b64encode(hashlib.sha384(data).digest()).decode("ascii")
        return f"sha384-{digest}"

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
    app.static_url_path = url_prefix(config.prefix)

    def serve_asset(filename):
        if not (app.env.development or app.env.test):
            return app.send_static_file(filename)
        try:
            path = pipeline.source_file(filename)
        except AssetError:
            abort(404)
        return send_from_directory(
            path.parent, path.name, max_age=app.get_send_file_max_age(filename)
        )

    app.add_url_rule(
        f"{app.static_url_path}/<path:filename>",
        endpoint="static",
        view_func=serve_asset,
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
