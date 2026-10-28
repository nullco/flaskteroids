"""Declarative module mappings, independent of Flask and package resolution."""

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

from flaskteroids._assets.paths import directory_path, logical_name, safe_path
from flaskteroids.importmaps.errors import ImportmapError


def module_name(name):
    if (
        not isinstance(name, str)
        or not name
        or name.startswith((".", "/"))
        or ":" in name.split("/")[0]
        or "\\" in name
        or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in name)
    ):
        raise ImportmapError(f"Expected a bare module name: {name!r}")
    return name


def module_url(value):
    if not isinstance(value, str) or any(
        char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value
    ):
        raise ImportmapError(f"Invalid module URL: {value!r}")
    url = urlsplit(value)
    if (
        url.scheme not in ("http", "https")
        or not url.hostname
        or url.username is not None
        or url.password is not None
    ):
        raise ImportmapError(f"Expected an HTTP(S) module URL: {value!r}")
    return value


def script_json(value):
    """JSON safe inside a script element, including literal closing tags."""
    return (
        json.dumps(value, ensure_ascii=True, indent=2)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _preload(value):
    if isinstance(value, list):
        value = tuple(value)
    if not isinstance(value, (bool, str, tuple)):
        raise ImportmapError("preload must be a boolean, entrypoint, or entrypoints")
    if not isinstance(value, bool):
        for entry in (value,) if isinstance(value, str) else value:
            module_name(entry)
    return value


def _integrity(value):
    if value is not None and not isinstance(value, (bool, str)):
        raise ImportmapError("integrity must be a boolean, hash, or None")
    if isinstance(value, str) and not re.fullmatch(
        r"sha(?:256|384|512)-[A-Za-z0-9+/]+=*", value
    ):
        raise ImportmapError("Invalid integrity hash")
    return value


@dataclass(frozen=True)
class Pin:
    name: str
    to: str
    preload: bool | str | tuple[str, ...] = True
    integrity: bool | str | None = True


@dataclass(frozen=True)
class DirectoryPin:
    directory: Path
    under: str | None
    to: str | None
    preload: bool | str | tuple[str, ...]
    integrity: bool | str | None


@dataclass(frozen=True)
class ResolvedPin:
    name: str
    url: str
    preload: bool | str | tuple[str, ...]
    integrity: str | None


@dataclass(frozen=True)
class ResolvedMap:
    pins: tuple[ResolvedPin, ...]

    def to_dict(self):
        result = {"imports": {pin.name: pin.url for pin in self.pins}}
        integrity = {pin.url: pin.integrity for pin in self.pins if pin.integrity}
        if integrity:
            result["integrity"] = integrity
        return result

    def preloads(self, entry_point="application"):
        selected = {}
        for pin in self.pins:
            preload = pin.preload
            enabled = preload is True or (
                preload is not False
                and entry_point in ((preload,) if isinstance(preload, str) else preload)
            )
            if enabled:
                selected[pin.url] = pin
        return tuple(selected.values())


class ImportMap:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self._pins = {}
        self._directories = {}
        self._integrity = False

    @classmethod
    def load(cls, root):
        importmap = cls(root)
        path = safe_path(importmap.root, "config/importmap.py")
        if path.is_file():
            # Execute source rather than import a globally cached application module.
            namespace = {"__file__": str(path), "__name__": "flaskteroids_importmap"}
            exec(
                compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace
            )
            register = namespace.get("register")
            if not callable(register):
                raise ImportmapError(f"{path} must define register(importmap)")
            register(importmap)
        return importmap

    def enable_integrity(self):
        self._integrity = True

    def pin(self, name, *, to=None, preload=True, integrity=True):
        module_name(name)
        target = to if to is not None else f"{name}.js"
        if not isinstance(target, str):
            raise ImportmapError(f"Invalid pin target: {target!r}")
        if target.startswith(("http:", "https:")):
            module_url(target)
        else:
            logical_name(target)
        self._pins[name] = Pin(name, target, _preload(preload), _integrity(integrity))

    def pin_all_from(
        self, directory, *, under=None, to=None, preload=True, integrity=True
    ):
        path = directory_path(self.root, directory)
        if under is not None:
            module_name(under)
        if to is not None and to != "":
            logical_name(to)
        self._directories[path] = DirectoryPin(
            path, under, to, _preload(preload), _integrity(integrity)
        )

    def pins(self):
        expanded = dict(self._pins)
        for mapping in self._directories.values():
            directory_path(self.root, mapping.directory)
            for path in sorted(mapping.directory.rglob("*")):
                relative = path.relative_to(mapping.directory)
                if any(part.startswith(".") for part in relative.parts):
                    continue
                safe_path(mapping.directory, relative.as_posix())
                if not path.is_file() or path.suffix not in (".js", ".mjs"):
                    continue
                parts = list(relative.with_suffix("").parts)
                if parts[-1] == "index":
                    parts.pop()
                name = "/".join(filter(None, (mapping.under, *parts)))
                module_name(name)
                target = "/".join(
                    filter(
                        None,
                        (
                            mapping.to if mapping.to is not None else mapping.under,
                            relative.as_posix(),
                        ),
                    )
                )
                expanded[name] = Pin(name, target, mapping.preload, mapping.integrity)
        return tuple(expanded.values())

    def resolve(self, resolver, *, integrity_resolver=None):
        resolved = []
        for pin in self.pins():
            external = pin.to.startswith(("http:", "https:"))
            url = pin.to if external else resolver(pin.to)
            integrity = None
            if self._integrity:
                if isinstance(pin.integrity, str):
                    integrity = pin.integrity
                elif pin.integrity is True and not external and integrity_resolver:
                    integrity = integrity_resolver(pin.to)
            resolved.append(ResolvedPin(pin.name, url, pin.preload, integrity))
        return ResolvedMap(tuple(resolved))

    def digest(self, resolver, *, integrity_resolver=None):
        resolved = self.resolve(resolver, integrity_resolver=integrity_resolver)
        return sha256(script_json(resolved.to_dict()).encode()).hexdigest()
