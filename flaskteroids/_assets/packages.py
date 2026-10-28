"""Public assets shipped by framework components, below application overrides."""

from importlib.resources import files
from pathlib import Path

from flaskteroids._assets.paths import safe_path

PUBLIC_ASSETS = {
    "turbo.js": ("flaskteroids.turbo", "assets/turbo.js"),
}


def packaged_assets():
    return {
        name: safe_path(Path(files(package)), path)
        for name, (package, path) in PUBLIC_ASSETS.items()
    }
