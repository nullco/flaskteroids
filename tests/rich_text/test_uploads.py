import io

import pytest
from flask import render_template_string

from flaskteroids.attachments import Blob
from tests.assertions import HTML
from tests.rich_text.app.models.document import Document

pytestmark = pytest.mark.usefixtures("app_ctx")


@pytest.fixture
def editor(app):
    app.config.controller.allow_forgery_protection = True

    @app.get("/upload-editor")
    def editor_form():
        return render_template_string(
            '{% call(form) form_with(model=record, url="/documents") %}'
            '{{ form.rich_text_area("content") }}{% endcall %}',
            record=Document.new(),
        )

    def load(client):
        parsed = HTML(client.get("/upload-editor").text)
        csrf = parsed.forms[0]["fields"]["csrf_token"]
        url = next(
            attrs["data-upload-url"]
            for tag, attrs in parsed.elements
            if tag == "trix-editor"
        )
        return url, csrf

    return load


def upload(client, url, csrf, *, data=b"file", filename="report.txt"):
    return client.post(
        url, data={"file": (io.BytesIO(data), filename)}, headers={"X-CSRF-TOKEN": csrf}
    )


def test_upload_uses_storage_and_returns_an_unattached_signed_embed(editor, client):
    url, csrf = editor(client)
    response = upload(client, url, csrf)
    assert response.status_code == 201
    attributes = response.json
    blob = Blob.find_signed_or_raise(attributes["sgid"], purpose="rich_text_attachable")
    assert blob.attachments == []
    assert blob.download() == b"file"
    assert attributes["filename"] == "report.txt"
    assert response.cache_control.no_store


def test_upload_requires_the_forms_browser_session(editor, app, client):
    url, csrf = editor(client)
    other = app.test_client()
    other_url, other_csrf = editor(other)
    assert upload(other, url, other_csrf).status_code == 404
    assert upload(other, other_url, other_csrf).status_code == 201


def test_upload_requires_a_valid_csrf_token(editor, client):
    url, csrf = editor(client)
    assert upload(client, url, "invalid").status_code == 400


def test_upload_rechecks_application_authorization(editor, client, app):
    url, csrf = editor(client)
    calls = []

    def deny(model, identity, name):
        calls.append((model, identity, name))
        return False

    app.config.rich_text.authorize_upload = deny
    assert upload(client, url, csrf).status_code == 404
    assert calls == [(Document, None, "content")]


def test_upload_rejects_expired_form_capabilities(editor, client, app):
    app.config.rich_text.upload_token_expires_in = -1
    url, csrf = editor(client)
    assert upload(client, url, csrf).status_code == 404


def test_upload_enforces_the_existing_storage_size_limit(editor, client, app):
    app.config.attachments.max_upload_size = 3
    url, csrf = editor(client)
    assert upload(client, url, csrf, data=b"large").status_code == 413


def test_private_embed_downloads_use_the_existing_authorization_callback(
    editor, client, app
):
    url, csrf = editor(client)
    uploaded = upload(client, url, csrf).json
    app.config.attachments.authorize = lambda blob: False
    assert client.get(uploaded["url"]).status_code == 404
