from datetime import UTC, datetime

from sqlalchemy import and_, inspect
from sqlalchemy.orm import relationship

from flaskteroids.declarations import model_for
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.rich_text.content import Content
from flaskteroids.rules import declaration


@declaration
def has_rich_text(name):
    if not isinstance(name, str) or not name.isidentifier() or name.startswith("_"):
        raise ProgrammerError("Rich-text names must be public Python identifiers")
    association = f"rich_text_{name}"
    scope = f"with_rich_text_{name}"

    def bind(cls):
        inherited = any(
            name in model_for(base).rich_texts
            for base in cls.__mro__[1:]
            if base is not object
        )
        for attribute in (name, association, scope):
            if attribute in dir(cls) and (not inherited or attribute in vars(cls)):
                raise ProgrammerError(
                    f"Rich text {name} conflicts with model attribute {attribute}"
                )
        definition = model_for(cls)
        if {name, association, scope} & (
            definition.attachments.keys()
            | definition.virtual_fields.keys()
            | definition.associations.keys()
        ):
            raise ProgrammerError(
                f"Rich text {name} conflicts with a model declaration"
            )
        model_for(cls).rich_texts.add(name)
        setattr(cls, name, property(lambda instance: read(instance, name)))
        setattr(cls, scope, classmethod(lambda owner: owner.includes(association)))

    return bind


def assign(instance, name, value):
    if name not in model_for(type(instance)).rich_texts:
        return False
    if value is None:
        value = Content()
    elif isinstance(value, str):
        value = Content(value)
    elif not isinstance(value, Content):
        raise TypeError(f"{name} expects an HTML string, Content, or None")
    instance._rich_text_changes[name] = value
    return True


def read(instance, name):
    if name in instance._rich_text_changes:
        return instance._rich_text_changes[name]
    row = None if instance.is_new_record() else getattr(instance, f"rich_text_{name}")
    if row is not None:
        return Content(row.body)
    content = Content()
    instance._rich_text_changes[name] = content
    return content


def relationship_properties(model, table, registry):
    names = model_for(model).rich_texts
    if not names:
        return {}
    rich_table = registry.metadata.tables.get("rich_texts")
    if rich_table is None:
        raise ProgrammerError(
            "Rich-text storage is missing from the schema snapshot. "
            "Run flask rich_text:install, then flask db:migrate and restart."
        )
    if len(table.primary_key) != 1 or "id" not in table.primary_key:
        raise ProgrammerError(
            "Rich text requires an owner with a single id primary key"
        )
    # One mapped storage class per application registry; SQLAlchemy owns loading,
    # identity, eager loading, expiration, and transactional rollback.
    row_type = next(
        (
            mapper.class_
            for mapper in registry.mappers
            if mapper.local_table is rich_table
        ),
        None,
    )
    if row_type is None:
        row_type = type("RichTextRow", (), {})
        registry.map_imperatively(row_type, rich_table)
    overlaps = {
        f"rich_text_{name}"
        for candidate in model._flaskteroids_model_root._flaskteroids_model_catalog.values()
        for name in model_for(candidate).rich_texts
    }
    return {
        f"rich_text_{name}": relationship(
            row_type,
            primaryjoin=and_(
                table.c.id == rich_table.c.record_id,
                rich_table.c.record_type == model.__name__,
                rich_table.c.name == name,
            ),
            foreign_keys=[rich_table.c.record_id],
            uselist=False,
            cascade="all, delete-orphan",
            single_parent=True,
            overlaps=",".join(sorted(overlaps)),
        )
        for name in sorted(names)
    }


def publish(instance):
    now = datetime.now(UTC)
    for name, content in instance._rich_text_changes.items():
        association = f"rich_text_{name}"
        row = getattr(instance, association)
        if row is None:
            row_type = inspect(type(instance)).relationships[association].mapper.class_
            row = row_type()
            row.name = name
            row.record_type = type(instance).__name__
            row.created_at = now
            setattr(instance, association, row)
        row.body = content._source
        row.updated_at = now
