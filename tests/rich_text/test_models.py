import pytest
from sqlalchemy import event, func, select

from flaskteroids.db import session
from flaskteroids.rich_text import Content
from tests.rich_text.app.models.document import Document
from tests.rich_text.app.models.note import Note

pytestmark = pytest.mark.usefixtures("app_ctx")


def row_count(app):
    table = app.extensions["flaskteroids.db"].metadata.tables["rich_texts"]
    return session.scalar(select(func.count()).select_from(table))


def test_save_persists_named_bodies_without_owner_columns(app):
    document = Document.create(
        title="Example", content="<div>Hello</div>", summary="<strong>Summary</strong>"
    )
    assert document.is_persisted()
    assert "content" not in document.column_names
    document.reload()
    assert document.content.to_plain_text() == "Hello"
    assert document.summary.to_plain_text() == "Summary"
    assert row_count(app) == 2


def test_assignment_stays_local_until_the_owner_is_saved():
    document = Document.create(title="Example", content="Original")
    document.content = "<div>Changed</div>"
    Note.create(title="Other", content="Other")
    with session.get_bind().connect() as connection:
        table = Document.metadata.tables["rich_texts"]
        assert (
            connection.scalar(
                select(table.c.body).where(table.c.record_type == "Document")
            )
            == "Original"
        )
    assert document.content.to_plain_text() == "Changed"
    assert document.save()
    assert document.reload().content.to_plain_text() == "Changed"


def test_validation_failure_keeps_submitted_content_for_correction(app):
    document = Document.create(title="Example", content="Original")
    assert not document.update(title="", content="<strong>Submitted</strong>")
    assert document.content.to_plain_text() == "Submitted"
    assert document.errors
    document.title = "Corrected"
    assert document.save()
    assert document.reload().content.to_trix_html() == "<strong>Submitted</strong>"
    assert row_count(app) == 1


@pytest.mark.parametrize("value", [None, "", "<div><br></div>", "<div>&nbsp;</div>"])
def test_presence_validation_rejects_empty_rich_text(value):
    document = Document.new(title="Example", content=value)
    assert not document.save()
    assert document.errors


def test_omitted_attributes_preserve_bodies_and_explicit_none_clears_optional_body():
    document = Document.create(title="Example", content="Main", summary="Summary")
    assert document.update(title="Updated")
    assert document.reload().summary.to_plain_text() == "Summary"
    assert document.update(summary=None)
    assert document.reload().summary.blank()


def test_destroy_removes_owned_bodies_and_preserves_other_record_types(app):
    document = Document.create(title="Example", content="Document")
    note = Note.create(title="Example", content="Note")
    assert document.id == note.id
    assert document.destroy()
    assert row_count(app) == 1
    assert note.reload().content.to_plain_text() == "Note"


def test_transaction_rollback_restores_persisted_body():
    document = Document.create(title="Example", content="Original")
    with pytest.raises(RuntimeError), Document.transaction():
        document.update(content="Changed")
        raise RuntimeError("Cancel")
    assert document.reload().content.to_plain_text() == "Original"


def test_savepoint_rollback_preserves_outer_body():
    document = Document.create(title="Example", content="Original")
    with Document.transaction():
        document.update(content="Outer")
        with pytest.raises(RuntimeError), Document.transaction(requires_new=True):
            document.update(content="Inner")
            raise RuntimeError("Cancel")
    assert document.reload().content.to_plain_text() == "Outer"


def test_reading_blank_content_builds_a_body_that_saves_with_its_owner(app):
    note = Note.new(title="Example")
    assert note.content.blank()
    assert row_count(app) == 0
    assert note.is_new_record()
    assert note.save()
    assert row_count(app) == 1
    assert note.reload().content.blank()


@pytest.mark.parametrize(
    "scope",
    [
        lambda: Document.with_rich_text_content(),
        lambda: Document.where(title="Example").with_rich_text_content(),
        lambda: Document.with_all_rich_text(),
        lambda: Document.includes("rich_text_content"),
    ],
)
def test_eager_loading_reads_bodies_without_per_record_queries(app, scope):
    for _ in range(3):
        Document.create(title="Example", content="Body")
    session.expunge_all()
    queries = []
    engine = app.extensions["flaskteroids.db"].engine

    def track(connection, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", track)
    try:
        records = list(scope())
        before = len(queries)
        assert [record.content.to_plain_text() for record in records] == ["Body"] * 3
        assert len(queries) == before
        assert before <= 4
    finally:
        event.remove(engine, "before_cursor_execute", track)


def test_content_assignment_accepts_content_values():
    document = Document.create(title="Example", content=Content("<em>Body</em>"))
    assert document.reload().content.to_trix_html() == "<em>Body</em>"


def test_owner_save_persists_new_associated_rich_text_bodies(app):
    document = Document.new(title="Example", content="Owner")
    note = Note.new(document=document, content="Associated")
    assert document.save()
    assert note.is_persisted()
    assert note.reload().content.to_plain_text() == "Associated"
    assert row_count(app) == 2


def test_callbacks_observe_the_saved_body_after_standalone_commit():
    document = Document.create(title="Example", content="<strong>Created</strong>")
    assert document.saved_content == "Created"
    assert document.committed_content == "Created"
    assert document.update(content="<em>Updated</em>")
    assert document.saved_content == "Updated"
    assert document.committed_content == "Updated"


def test_commit_callback_waits_for_the_owner_transaction():
    document = Document.create(title="Example", content="Original")
    with Document.transaction():
        document.update(content="Changed")
        assert document.saved_content == "Changed"
        assert document.committed_content == "Original"
    assert document.committed_content == "Changed"


def test_rich_text_filters_reject_noncolumn_attributes():
    with pytest.raises(ValueError, match="not searchable scalar columns"):
        Document.where(content="Body")


def test_content_assignment_rejects_structured_values():
    with pytest.raises(TypeError):
        Document.new(title="Example", content={"html": "Body"})
