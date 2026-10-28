"""Safe HTML for browser-native module loading."""

from hashlib import sha256

from markupsafe import Markup

from flaskteroids._html import attributes
from flaskteroids.importmaps.extension import resolved_importmap
from flaskteroids.importmaps.map import module_name, script_json


def importmap_digest():
    """Include this digest in manually managed HTML validators."""
    return sha256(script_json(resolved_importmap().to_dict()).encode()).hexdigest()


def javascript_inline_importmap_tag(importmap=None, *, nonce=None):
    data = resolved_importmap().to_dict() if importmap is None else importmap
    attrs = attributes(
        {"type": "importmap", "data-turbo-track": "reload", "nonce": nonce}
    )
    return Markup(f"<script {attrs}>{script_json(data)}</script>")


def javascript_import_module_tag(*module_names, nonce=None):
    imports = "\n".join(
        f"import {script_json(module_name(name))};" for name in module_names
    )
    return Markup(
        f"<script {attributes({'type': 'module', 'nonce': nonce})}>{imports}</script>"
    )


def javascript_module_preload_tag(*paths, nonce=None):
    return Markup(
        "\n".join(
            f"<link {attributes({'rel': 'modulepreload', 'href': path, 'nonce': nonce})}>"
            for path in paths
        )
    )


def _preload_tags(importmap, entry_point, nonce):
    return "\n".join(
        f"<link {attributes({'rel': 'modulepreload', 'href': pin.url, 'integrity': pin.integrity, 'nonce': nonce})}>"
        for pin in importmap.preloads(entry_point)
    )


def javascript_importmap_tags(entry_point="application", *, nonce=None):
    importmap = resolved_importmap()
    if entry_point not in importmap.to_dict()["imports"]:
        raise ValueError(f"Entrypoint is not pinned: {entry_point}")
    return Markup(
        "\n".join(
            (
                str(javascript_inline_importmap_tag(importmap.to_dict(), nonce=nonce)),
                _preload_tags(importmap, entry_point, nonce),
                str(javascript_import_module_tag(entry_point, nonce=nonce)),
            )
        )
    )
