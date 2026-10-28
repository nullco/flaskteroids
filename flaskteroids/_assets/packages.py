"""Public assets shipped by framework components, below application overrides."""

from importlib.metadata import entry_points
from importlib.resources import files
from pathlib import Path

from flaskteroids._assets.paths import safe_path

PUBLIC_ASSETS = {
    name: ("flaskteroids.rich_text", f"assets/{name}")
    for name in ("rich_text.js", "rich_text.css", "rich_text_uploads.js")
}


def packaged_assets():
    exposed = dict(PUBLIC_ASSETS)
    for entry in entry_points(group="flaskteroids.assets"):
        for name, source in entry.load().items():
            if name in exposed:
                raise ValueError(f"Duplicate packaged asset: {name}")
            exposed[name] = source
    return {
        name: safe_path(Path(files(package)), path)
        for name, (package, path) in exposed.items()
    }
