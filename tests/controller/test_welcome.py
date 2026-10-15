from base64 import b64decode
from html.parser import HTMLParser
from importlib.resources import files
from xml.etree import ElementTree

import pytest

from flaskteroids import __version__


@pytest.fixture
def welcome_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.mimetype == "text/html"

    class Page(HTMLParser):
        def __init__(self):
            super().__init__()
            self.elements = []

        def handle_starttag(self, tag, attrs):
            self.elements.append((tag, dict(attrs)))

    page = Page()
    html = response.get_data(as_text=True)
    page.feed(html)
    return html, page.elements


def test_welcome_shows_logo_version_and_documentation(welcome_page):
    html, elements = welcome_page

    assert "<title>Welcome to Flaskteroids</title>" in html
    assert f"v{__version__}" in html
    assert "Your app is running." in html
    assert sum(tag == "h1" for tag, _ in elements) == 1
    assert any(
        tag == "img" and attrs.get("alt") == "Flaskteroids" for tag, attrs in elements
    )
    assert any(
        tag == "a" and attrs["href"] == "https://nullco.github.io/flaskteroids/"
        for tag, attrs in elements
    )


def test_welcome_bundles_light_dark_logos_and_favicon(welcome_page):
    _, elements = welcome_page
    images = {
        "logo-horizontal-light": next(
            attrs["src"] for tag, attrs in elements if tag == "img"
        ),
        "logo-horizontal-dark": next(
            attrs["srcset"] for tag, attrs in elements if tag == "source"
        ),
        "favicon": next(
            attrs["href"]
            for tag, attrs in elements
            if tag == "link" and attrs.get("rel") == "icon"
        ),
    }

    for name, url in images.items():
        prefix, data = url.split(",", 1)
        assert prefix == "data:image/svg+xml;base64"
        svg = b64decode(data)
        assert ElementTree.fromstring(svg).tag == "{http://www.w3.org/2000/svg}svg"
        assert svg == (
            files("flaskteroids")
            .joinpath(f"controllers/templates/brand/{name}.svg")
            .read_bytes()
        )

    assert any(
        tag == "source" and attrs["media"] == "(prefers-color-scheme: dark)"
        for tag, attrs in elements
    )
    assert not any(
        tag in {"script", "style"} and "src" in attrs for tag, attrs in elements
    )
    assert not any(
        tag == "link" and attrs.get("rel") == "stylesheet" for tag, attrs in elements
    )


@pytest.mark.parametrize(
    ("version", "label"), [("9.8.7", "v9.8.7"), (None, "development")]
)
def test_welcome_version_label(client, mocker, version, label):
    mocker.patch("flaskteroids.controllers.welcome_controller.version", version)

    response = client.get("/")

    assert response.status_code == 200
    assert label in response.get_data(as_text=True)
