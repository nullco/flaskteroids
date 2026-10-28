"""Configure the packaged editor without replacing application JavaScript."""

import re
from pathlib import Path

from flaskteroids._assets.paths import safe_path
from flaskteroids.importmaps.configuration import PinFile
from flaskteroids.importmaps.errors import ImportmapError
from flaskteroids.importmaps.installation import Installation
from flaskteroids.importmaps.installation import install as install_importmap

PINS = {
    "lexxy": "lexxy.js",
    "flaskteroids/rich-text": "rich_text.js",
    "@rails/activestorage": "rich_text_uploads.js",
}
MODULE = "flaskteroids/rich-text"


def install_javascript(root, *, views_path="app/views"):
    root = Path(root).resolve()
    result = install_importmap(root, views_path=views_path)
    created, instructions = list(result.files), list(result.instructions)
    path = safe_path(root, "config/importmap.py")
    try:
        editor = PinFile(path)
        configuration = editor.render_local_pins(PINS)
    except (ImportmapError, SyntaxError) as error:
        instructions.append(f"Configure rich-text pins manually ({error}): {PINS}")
    else:
        if configuration != editor.source:
            path.write_text(configuration)
            created.append(path)
    path = safe_path(root, "app/javascript/application.js")
    source = path.read_text()
    if not re.search(
        rf"^\s*import\s+(?:[^\n;]+?\s+from\s+)?[\"']{re.escape(MODULE)}[\"']",
        source,
        flags=re.M,
    ):
        path.write_text(
            source + ("" if source.endswith("\n") else "\n") + f'import "{MODULE}"\n'
        )
        created.append(path)
    return Installation(tuple(created), tuple(instructions))
