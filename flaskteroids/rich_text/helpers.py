from markupsafe import Markup

from flaskteroids._html import attributes
from flaskteroids.assets import asset_path, stylesheet_link_tag


def rich_text_assets():
    """Include the locally installed Trix editor and attachment integration."""
    tags = [stylesheet_link_tag("rich_text/trix.css", "rich_text/rich_text.css")]
    for name in ("rich_text/rich_text.js", "rich_text/trix.js"):
        attrs = attributes(
            {"src": asset_path(name), "defer": "defer", "data-turbo-track": "reload"}
        )
        tags.append(Markup(f"<script {attrs}></script>"))
    return Markup("\n").join(tags)
