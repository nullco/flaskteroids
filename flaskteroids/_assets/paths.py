"""Shared path boundaries for public application assets."""

from pathlib import Path

from werkzeug.security import safe_join


class AssetError(ValueError):
    pass


def logical_name(name):
    if (
        not isinstance(name, str)
        or not name
        or "\\" in name
        or any(ord(char) < 32 or ord(char) == 127 for char in name)
        or any(part.startswith(".") or not part for part in name.split("/"))
    ):
        raise AssetError(f"Invalid asset name: {name!r}")
    return name


def url_prefix(value):
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or any(char in value for char in "?#%")
    ):
        raise AssetError(
            "Asset URL prefix must be an absolute path without query strings"
        )
    logical_name(value.rstrip("/")[1:])
    return value


def safe_path(directory, name):
    joined = safe_join(str(directory), name)
    if joined is None:
        raise AssetError(f"Asset path escapes its directory: {name!r}")
    path = directory
    for part in Path(joined).relative_to(directory).parts:
        path = path / part
        if path.is_symlink():
            raise AssetError(f"Asset symlinks are not supported: {path}")
    return path


def directory_path(root, name):
    path = root / name
    if not path.is_relative_to(root):
        raise AssetError("Asset directories must be inside the application root")
    path = safe_path(root, path.relative_to(root).as_posix())
    if path.resolve() == root or (path.exists() and not path.is_dir()):
        raise AssetError(f"Invalid asset directory: {path}")
    return path
