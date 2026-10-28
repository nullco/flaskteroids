"""Development-time package resolution and vendoring, never used by page requests."""

import json
import os
import re
import stat
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from flaskteroids._assets.paths import directory_path, logical_name, safe_path
from flaskteroids.importmaps.configuration import PackagePin, PinFile
from flaskteroids.importmaps.errors import ImportmapError
from flaskteroids.importmaps.map import module_name, module_url

JSPM_ENDPOINT = "https://api.jspm.io/generate"
PROVIDERS = {"jspm": "jspm.io", "jsdelivr": "jsdelivr", "unpkg": "unpkg"}
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024


def _https(url):
    module_url(url)
    if not url.startswith("https://"):
        raise ImportmapError(f"Package requests require HTTPS: {url}")
    return url


class _HTTPSRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _https(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HTTPClient:
    def request(self, url, *, body=None):
        _https(url)
        request = Request(
            url,
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Flaskteroids importmap",
            },
        )
        try:
            with build_opener(_HTTPSRedirects()).open(request, timeout=30) as response:
                _https(response.url)
                data = response.read(MAX_DOWNLOAD_BYTES + 1)
        except (HTTPError, URLError, OSError) as error:
            raise ImportmapError(
                f"Package request failed for {url}: {error}"
            ) from error
        if len(data) > MAX_DOWNLOAD_BYTES:
            raise ImportmapError(f"Package response exceeds 20 MiB: {url}")
        return data

    def json(self, url, *, body=None):
        data = self.request(url, body=body)
        try:
            result = json.loads(data)
        except (ValueError, UnicodeError) as error:
            raise ImportmapError(f"Invalid JSON response from {url}") from error
        if not isinstance(result, dict):
            raise ImportmapError(f"Expected a JSON object from {url}")
        return result


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        staged = Path(temporary.name)
        try:
            temporary.write(data)
            temporary.close()
            mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
            staged.chmod(mode)
            os.replace(staged, path)
        finally:
            staged.unlink(missing_ok=True)


class Packager:
    def __init__(self, root, *, client=None):
        self.root = Path(root).resolve()
        self.client = client if client is not None else HTTPClient()
        self.config_path = safe_path(self.root, "config/importmap.py")
        self.vendor = directory_path(self.root, "vendor/javascript")

    def pin(self, *packages, provider="jspm", environment="production", preload=None):
        if not packages:
            raise ImportmapError("Specify at least one package")
        if provider not in PROVIDERS:
            raise ImportmapError(f"Unknown package provider: {provider}")
        for package in packages:
            if not isinstance(package, str) or not re.fullmatch(
                r"(?:@[A-Za-z0-9_.-]+/)?[A-Za-z0-9_][A-Za-z0-9_.-]*(?:/[^\s@]+)*(?:@[^\s]+)?",
                package,
            ):
                raise ImportmapError(f"Invalid package request: {package!r}")
        editor = PinFile(self.config_path)
        result = self.client.json(
            JSPM_ENDPOINT,
            body={
                "install": list(packages),
                "flattenScope": True,
                "env": ["browser", "module", environment],
                "provider": PROVIDERS[provider],
            },
        )
        mapping = result.get("map")
        if (
            not isinstance(mapping, dict)
            or not isinstance(mapping.get("imports"), dict)
            or not mapping["imports"]
            or mapping.get("scopes")
        ):
            raise ImportmapError(
                f"Package resolution did not return a flattened import map: {result.get('error', '')}"
            )
        downloads = {}
        pins = []
        existing_targets = editor.filenames()
        for name, url in mapping["imports"].items():
            module_name(name)
            filename = logical_name(name.replace("/", "--") + ".js")
            target = safe_path(self.vendor, filename)
            if target in downloads or (
                existing_targets.get(name) != filename
                and any(
                    existing_filename == filename
                    and existing_name not in mapping["imports"]
                    for existing_name, existing_filename in existing_targets.items()
                )
            ):
                raise ImportmapError(f"Packages have colliding filenames: {name}")
            for source in ("app/javascript", "app/assets"):
                if safe_path(self.root, f"{source}/{filename}").exists():
                    raise ImportmapError(
                        f"Downloaded asset conflicts with {source}/{filename}"
                    )
            _https(url)
            match = re.search(r"@(\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?)", url)
            version = match[1] if match else None
            source = self.client.request(url)
            try:
                text = source.decode("utf-8")
            except UnicodeError as error:
                raise ImportmapError(
                    f"Package is not UTF-8 JavaScript: {url}"
                ) from error
            text = re.sub(r"^//# sourceMappingURL=.*\n?", "", text, flags=re.MULTILINE)
            downloads[target] = (
                f"// {name}@{version or 'unknown'} downloaded from {url}\n\n{text}"
            ).encode()
            pins.append(PackagePin(name, filename, version))
        configuration = editor.render(pins, preload=preload).encode()
        # Complete resolution, validation, and downloads before changing any app files.
        for target, data in downloads.items():
            atomic_write(target, data)
        atomic_write(self.config_path, configuration)
        return tuple(pins)

    def unpin(self, *names):
        editor = PinFile(self.config_path)
        managed = {pin.name: pin for pin in editor.packages()}
        removed = set(names) & editor.declarations.keys()
        retained_files = {
            filename
            for name, filename in editor.filenames().items()
            if name not in removed
        }
        targets = []
        for name in removed:
            if name in managed and managed[name].filename not in retained_files:
                filename = logical_name(managed[name].filename)
                targets.append(safe_path(self.vendor, filename))
        configuration = editor.render(remove=removed).encode()
        atomic_write(self.config_path, configuration)
        for path in targets:
            path.unlink(missing_ok=True)
        return tuple(sorted(removed))

    def packages(self):
        return PinFile(self.config_path).packages()

    def pristine(self, *, provider="jspm"):
        packages = self.packages()
        if not packages:
            return ()
        requests = [
            f"{pin.name}@{pin.version}"
            if pin.version not in (None, "unknown")
            else pin.name
            for pin in packages
        ]
        return self.pin(*requests, provider=provider)

    def update(self, *, provider="jspm"):
        packages = self.packages()
        return (
            self.pin(*(pin.name for pin in packages), provider=provider)
            if packages
            else ()
        )
