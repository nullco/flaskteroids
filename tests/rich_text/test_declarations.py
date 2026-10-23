import pytest
from sqlalchemy import select
from sqlalchemy.orm import aliased

from flaskteroids.exceptions import ProgrammerError
from flaskteroids.model import Model, has_rich_text


@pytest.mark.parametrize("name", ["save", "title", "with_all_rich_text"])
def test_rich_text_declaration_rejects_conflicting_model_names(name):
    class Base(Model):
        __abstract__ = True
        __schema_module__ = "tests.rich_text.db.schema"

    class Document(Base):
        __table_name__ = "documents"
        has_rich_text(name)

    with pytest.raises(ProgrammerError):
        Document.prepare()


@pytest.mark.parametrize("name", ["", "_content", "not-valid", None])
def test_rich_text_declaration_rejects_invalid_names(name):
    with pytest.raises(ProgrammerError):

        class Invalid:
            has_rich_text(name)


def test_abstract_model_declarations_supply_independent_rich_text_fields():
    class Base(Model):
        __abstract__ = True
        __schema_module__ = "tests.rich_text.db.schema"
        has_rich_text("content")

    class Document(Base):
        __table_name__ = "documents"

    class Note(Base):
        __table_name__ = "notes"

    document = Document.new(content="Document")
    note = Note.new(content="Note")
    assert document.content.to_plain_text() == "Document"
    assert note.content.to_plain_text() == "Note"


def test_missing_rich_text_storage_explains_the_installation_workflow():
    class Base(Model):
        __abstract__ = True
        __schema_module__ = "tests.attachments.db.schema"

    class Document(Base):
        __table_name__ = "documents"
        has_rich_text("content")

    with pytest.raises(ProgrammerError, match="rich_text:install"):
        Document.prepare()


def test_native_aliased_queries_use_only_the_aliased_owner_table():
    class Base(Model):
        __abstract__ = True
        __schema_module__ = "tests.rich_text.db.schema"

    class Document(Base):
        __table_name__ = "documents"
        has_rich_text("content")

    Document.prepare()
    owner = aliased(Document)
    statement = select(owner)
    assert len(statement.get_final_froms()) == 1
    assert statement.get_final_froms()[0].original is Document.__table__
