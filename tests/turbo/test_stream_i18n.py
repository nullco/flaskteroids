import pytest
from flask import render_template
from jinja2 import DictLoader


@pytest.mark.parametrize("extension", ["html", "turbo_stream.html"])
@pytest.mark.parametrize("name", ["create", "_post"])
def test_relative_translations_use_the_logical_view_path(
    view_app_factory, tmp_path, extension, name
):
    catalogs = tmp_path / "config/locales"
    catalogs.mkdir(parents=True)
    (catalogs / "en.yml").write_text(
        "en:\n  posts:\n    create:\n      title: Created\n    post:\n      title: Post\n"
    )
    app = view_app_factory(owners=False)
    template = f"posts/{name}.{extension}"
    app.jinja_loader = DictLoader({template: "{{ t('.title') }}"})
    with app.app_context():
        assert render_template(template) == ("Created" if name == "create" else "Post")
