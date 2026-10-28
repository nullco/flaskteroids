from flaskteroids.assets import stylesheet_link_tag


def rich_text_assets():
    """Include the packaged editor and rendered-content stylesheets."""
    return stylesheet_link_tag(
        "lexxy.css", "rich_text.css", **{"data-turbo-track": "reload"}
    )
