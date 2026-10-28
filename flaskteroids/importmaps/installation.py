"""Install conventions conservatively; application code is never overwritten."""

import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from flaskteroids._assets.paths import safe_path

APPLICATION_PATHS = (
    "config/importmap.py",
    "app/javascript/application.js",
    "bin/importmap",
)
HELPER = "{{ javascript_importmap_tags() }}"


def application_files():
    templates = files("flaskteroids.importmaps").joinpath("templates")
    return {path: templates.joinpath(path).read_text() for path in APPLICATION_PATHS}


@dataclass(frozen=True)
class Installation:
    files: tuple[Path, ...]
    instructions: tuple[str, ...]


def install(root, *, views_path="app/views"):
    root = Path(root).resolve()
    created = []
    for name, content in application_files().items():
        target = safe_path(root, name)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            created.append(target)
        if name.startswith("bin/"):
            target.chmod(target.stat().st_mode | 0o111)
    vendor = safe_path(root, "vendor/javascript/.keep")
    if not vendor.exists():
        vendor.parent.mkdir(parents=True, exist_ok=True)
        vendor.touch()
        created.append(vendor)
    layout = safe_path(root, f"{views_path}/layouts/application.html")
    text = layout.read_text() if layout.exists() else ""
    instructions = []
    updated = text
    if "javascript_importmap_tags" not in text:
        if "<script" not in text.lower():
            updated = re.sub(
                r"</head\s*>", HELPER + "\n  </head>", text, count=1, flags=re.I
            )
        if "javascript_importmap_tags" not in updated:
            instructions.append(
                f"Add {HELPER} to your layout head and review existing scripts. "
                "Load only one Turbo runtime."
            )
    if "javascript_importmap_tags" in updated and not re.search(
        r"name\s*=\s*['\"]csrf-token['\"]", updated, flags=re.I
    ):
        updated = re.sub(
            r"</head\s*>",
            '    <meta name="csrf-token" content="{{ csrf_token() }}">\n  </head>',
            updated,
            count=1,
            flags=re.I,
        )
    if updated != text:
        layout.write_text(updated)
        created.append(layout)
    instructions.append(
        'Ensure config/importmap.py pins "application" and "@hotwired/turbo" '
        '(to="turbo.js"), and app/javascript/application.js imports "@hotwired/turbo".'
    )
    return Installation(tuple(created), tuple(instructions))
