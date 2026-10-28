"""Public assets shipped by framework components, below application overrides."""

from importlib.resources import files
from pathlib import Path

from flaskteroids._assets.paths import safe_path

PUBLIC_ASSETS = {
    "turbo.js": ("flaskteroids.turbo", "assets/turbo.js"),
    **{
        name: ("flaskteroids.rich_text", f"assets/{name}")
        for name in (
            "lexxy.js",
            "lexxy.css",
            "lexxy-content.css",
            "lexxy-editor.css",
            "lexxy-variables.css",
            "rich_text.js",
            "rich_text.css",
            "rich_text_uploads.js",
        )
    },
}


def packaged_assets():
    return {
        name: safe_path(Path(files(package)), path)
        for name, (package, path) in PUBLIC_ASSETS.items()
    }
