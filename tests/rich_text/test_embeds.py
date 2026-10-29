import base64
import io

import pytest
from sqlalchemy import event

from flaskteroids.attachments import Blob
from flaskteroids.db import session
from flaskteroids.exceptions import StrictLoadingViolationError
from flaskteroids.rich_text import Content
from tests.assertions import HTML
from tests.rich_text.app.models.document import Document
from tests.rich_text.app.models.entry import Entry
from tests.rich_text.app.models.note import Note

pytestmark = pytest.mark.usefixtures("app_ctx")
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aK1sAAAAASUVORK5CYII="
)


@pytest.fixture
def blob():
    return Blob.create_and_upload(io=io.BytesIO(PNG), filename="image.png")


def with_blob(blob):
    return Content("<div>Body</div>").append_attachables([blob])


def test_body_owns_signed_embeds_and_renders_safe_storage_urls(blob, app):
    owner = Document.create(title="Example", content=with_blob(blob))
    rich = owner.content
    assert [item.id for item in rich.embeds.blobs] == [blob.id]
    with app.test_request_context():
        rendered = HTML(str(owner.reload().content))
        assert rendered.has("img")
        image = next(attrs for tag, attrs in rendered.elements if tag == "img")
        assert image["src"].startswith("/flaskteroids/attachments/")
    assert "action-text-attachment" in rich.body.to_html()
    assert "image.png" in rich.to_plain_text()


def test_editor_html_roundtrips_only_verified_metadata(blob, app):
    forged = (
        f'<action-text-attachment sgid="{blob.attachable_sgid}" '
        'url="javascript:evil()" filename="fake" content-type="text/html" '
        'caption="A caption"><script>evil()</script></action-text-attachment>'
    )
    owner = Note.create(content=forged)
    with app.test_request_context():
        html = owner.content.to_editor_html()
        assert "javascript:" not in html
        assert "<script>" not in html
        assert "fake" not in html
        reloaded = Content(html)
        assert [item.id for item in reloaded.attachables] == [blob.id]
        assert "A caption" in reloaded.to_plain_text()


def test_attachment_captions_normalize_invalid_unicode(blob, app):
    body = (
        f'<action-text-attachment sgid="{blob.attachable_sgid}" '
        f'caption="{chr(0xD800)}"></action-text-attachment>'
    )
    owner = Note.create(content=body)
    with app.test_request_context():
        assert "?" in HTML(str(owner.content)).text


def test_attachment_captions_alternative_text_and_links_roundtrip(blob, app):
    body = (
        f'<action-text-attachment sgid="{blob.attachable_sgid}" '
        'caption="A caption" alt="An alternative" href="https://example.com">'
        "</action-text-attachment>"
    )
    owner = Note.create(content=body)
    with app.test_request_context():
        display = HTML(str(owner.content))
        assert display.has("img", alt="An alternative")
        assert display.has("a", href="https://example.com")
        editor = HTML(owner.content.to_editor_html())
        assert editor.has(
            "action-text-attachment", alt="An alternative", caption="A caption"
        )
        assert (
            Content(owner.content.to_editor_html()).to_html()
            == owner.content.body.to_html()
        )


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,evil"])
def test_attachment_links_reject_executable_urls(blob, app, url):
    owner = Note.create(
        content=f'<action-text-attachment sgid="{blob.attachable_sgid}" '
        f'href="{url}"></action-text-attachment>'
    )
    with app.test_request_context():
        assert url not in owner.content.body.to_html()
        assert url not in str(owner.content)
        assert url not in owner.content.to_editor_html()


def test_attachment_markup_escapes_captions_and_alternative_text(blob, app):
    owner = Note.create(
        content=f'<action-text-attachment sgid="{blob.attachable_sgid}" '
        'caption="&lt;script&gt;evil()&lt;/script&gt;" '
        'alt="&quot; onerror=&quot;evil()"></action-text-attachment>'
    )
    with app.test_request_context():
        display = HTML(str(owner.content))
        assert not display.has("script")
        image = next(attrs for tag, attrs in display.elements if tag == "img")
        assert "onerror" not in image
        assert image["alt"] == '" onerror="evil()'


def test_rendering_groups_adjacent_images_into_a_gallery(blob, app):
    owner = Note.create(content=Content().append_attachables([blob, blob]))
    with app.test_request_context():
        rendered = HTML(str(owner.content))
        assert rendered.has("div", **{"class": "attachment-gallery"})
        assert sum(tag == "img" for tag, attrs in rendered.elements) == 2
    assert len(owner.content.embeds.blobs) == 1


def test_binary_content_is_a_download_link_instead_of_an_inline_image(app):
    blob = Blob.create_and_upload(
        io=io.BytesIO(b"<svg><script>evil()</script></svg>"), filename="image.svg"
    )
    owner = Note.create(content=with_blob(blob))
    with app.test_request_context():
        rendered = HTML(str(owner.content))
        assert not rendered.has("img")
        editor = HTML(owner.content.to_editor_html())
        assert editor.has(
            "action-text-attachment",
            **{"content-type": "application/octet-stream", "previewable": "false"},
        )
        link = next(attrs["href"] for tag, attrs in rendered.elements if tag == "a")
    with app.test_client().get(link, follow_redirects=True) as response:
        assert response.headers["Content-Disposition"].startswith("attachment")


def test_normal_blob_signatures_are_not_accepted_as_embed_capabilities(blob):
    body = Content(
        f'<action-text-attachment sgid="{blob.signed_id()}"></action-text-attachment>'
    )
    assert body.attachables == []
    assert body.blank()


def test_failed_validation_keeps_uploaded_embeds_unattached_until_correction(blob):
    owner = Document.create(title="", content=with_blob(blob))
    assert owner.is_new_record()
    assert [item.id for item in owner.content.body.attachables] == [blob.id]
    assert blob.attachments == []
    owner.title = "Corrected"
    assert owner.save()
    assert len(blob.attachments) == 1


def test_embed_removal_purges_only_after_commit_and_preserves_shared_blobs(blob, app):
    first = Note.create(content=with_blob(blob))
    second = Note.create(content=with_blob(blob))
    jobs = app.extensions["flaskteroids.jobs"].queue_adapter
    jobs.clear()
    with Note.transaction():
        assert first.update(content="Removed")
        assert jobs.enqueued_jobs == []
    assert jobs.enqueued_jobs
    assert [item.record_id for item in blob.attachments] == [second.content.id]
    jobs.perform_all()
    assert blob.download() == PNG


def test_rollback_restores_removed_embeds_without_purge_jobs(blob, app):
    owner = Note.create(content=with_blob(blob))
    jobs = app.extensions["flaskteroids.jobs"].queue_adapter
    jobs.clear()
    with pytest.raises(RuntimeError), Note.transaction():
        owner.update(content="Removed")
        raise RuntimeError("Cancel")
    assert app.extensions["flaskteroids.jobs"].queue_adapter.enqueued_jobs == []
    assert [item.id for item in owner.reload().content.embeds.blobs] == [blob.id]


def test_owner_destroy_removes_embed_metadata_and_enqueues_purge(blob, app):
    owner = Note.create(content=with_blob(blob))
    assert owner.destroy()
    assert blob.attachments == []
    assert app.extensions["flaskteroids.jobs"].queue_adapter.enqueued_jobs


@pytest.mark.parametrize(
    "scope",
    [
        lambda document: Note.with_rich_text_content_and_embeds(),
        lambda document: Note.where(
            title="Example"
        ).with_rich_text_content_and_embeds(),
        lambda document: Note.with_all_rich_text(),
        lambda document: document.notes.with_rich_text_embeds("content"),
        lambda document: document.notes.with_all_rich_text(),
    ],
)
def test_embed_preloading_avoids_per_record_and_per_blob_queries(blob, app, scope):
    document = Document.create(title="Example", content="Document")
    for _ in range(3):
        Note.create(title="Example", document=document, content=with_blob(blob))
    session.expunge_all()
    queries = []
    engine = app.extensions["flaskteroids.db"].engine

    def track(connection, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", track)
    try:
        owners = list(scope(document))
        before = len(queries)
        with app.test_request_context():
            assert all(HTML(str(owner.content)).has("img") for owner in owners)
            assert all(owner.content.embeds.blobs[0].id == blob.id for owner in owners)
        assert len(queries) == before
        assert before == 3
    finally:
        event.remove(engine, "before_cursor_execute", track)


def test_strict_embed_loading_requires_the_embed_scope(blob):
    owner = Entry.create(restricted=with_blob(blob))
    identity = owner.id
    session.expunge_all()
    loaded = Entry.with_rich_text_restricted().find(identity)
    with pytest.raises(StrictLoadingViolationError):
        _ = loaded.restricted.body.attachables
    loaded = Entry.with_rich_text_restricted_and_embeds().find(identity)
    assert [item.id for item in loaded.restricted.body.attachables] == [blob.id]
