import pytest
from sqlalchemy import select

from flaskteroids.db import session
from flaskteroids.rich_text import Content, RichText
from tests.rich_text.app.models.document import Document
from tests.rich_text.app.models.note import Note

pytestmark = pytest.mark.usefixtures("app_ctx")


def test_attribute_returns_the_same_editable_record_and_content_body():
    owner = Note.new(title="Example", content="<strong>Body</strong>")
    rich = owner.content
    assert isinstance(rich, RichText)
    assert isinstance(rich.body, Content)
    assert owner.content is rich
    assert owner.rich_text_content is rich
    rich.body = "<em>Changed</em>"
    assert owner.save()
    assert owner.content is rich
    assert rich.is_persisted()
    assert rich.record is owner
    assert rich.reload().to_plain_text() == "Changed"


def test_independent_save_persists_body_without_saving_invalid_owner_input():
    owner = Document.create(title="Original", content="Body")
    owner.title = ""
    rich = owner.content
    rich.body = "<em>Independently saved</em>"
    assert rich.save()
    assert owner.title == ""
    with session.get_bind().connect() as connection:
        assert connection.scalar(select(Document.__table__.c.title)) == "Original"
    assert rich.reload().to_plain_text() == "Independently saved"


def test_independent_save_touches_its_owner():
    owner = Note.create(title="Example", content="Original")
    before = owner.updated_at
    assert owner.content.update(body="Changed")
    assert owner.updated_at > before


def test_independent_save_of_new_owner_creates_both_records():
    owner = Note.new(title="New", content="Body")
    assert owner.content.save()
    assert owner.is_persisted()
    assert owner.content.reload().to_plain_text() == "Body"


def test_independent_save_of_invalid_new_owner_retains_the_unsaved_body():
    owner = Document.new(title="", content="Body")
    rich = owner.content
    assert not rich.save()
    assert rich.errors
    assert rich.is_new_record()
    assert owner.is_new_record()
    assert rich.to_plain_text() == "Body"
    owner.title = "Corrected"
    assert rich.save()


def test_find_returns_the_same_record_with_its_owner():
    owner = Note.create(title="Example", content="Body")
    identity = owner.content.id
    session.expunge_all()
    rich = RichText.find(identity)
    assert rich.record.id == owner.id
    assert rich.record.content is rich
    rich.body = "Found"
    assert rich.record.save()
    assert rich.reload().to_plain_text() == "Found"


def test_independent_destroy_leaves_owner_and_an_empty_lazy_body():
    owner = Note.create(title="Example", content="Body")
    rich = owner.content
    assert rich.destroy()
    assert owner.is_persisted()
    assert owner.content.is_new_record()
    assert owner.content.blank()


@pytest.mark.parametrize("operation", ["save", "reload", "destroy"])
def test_rich_text_operations_reject_an_unregistered_owner(app, mocker, operation):
    from flaskteroids.exceptions import ProgrammerError

    owner = Note.create(title="Example", content="Body")
    rich = owner.content
    mocker.patch.object(
        app.extensions["flaskteroids.db"],
        "require_model",
        side_effect=ProgrammerError("Owner belongs to another application"),
    )
    with pytest.raises(ProgrammerError):
        getattr(rich, operation)()


def test_independent_save_joins_the_owner_transaction():
    owner = Note.create(title="Example", content="Original")
    with pytest.raises(RuntimeError), Note.transaction():
        owner.content.update(body="Rolled back")
        raise RuntimeError("Cancel")
    assert owner.reload().content.to_plain_text() == "Original"
