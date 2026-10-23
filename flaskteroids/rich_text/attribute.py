from sqlalchemy import and_, inspect
from sqlalchemy.orm import attributes, relationship
from sqlalchemy.orm.attributes import NO_VALUE

from flaskteroids.attachments import attached as attached_storage
from flaskteroids.db import session
from flaskteroids.declarations import RichTextDefinition, model_for
from flaskteroids.exceptions import ProgrammerError, StrictLoadingViolationError
from flaskteroids.rich_text.content import Content
from flaskteroids.rules import bind_rules, declaration


@declaration
def has_rich_text(name, *, encrypted=False, strict_loading=None, store_if_blank=True):
    if not isinstance(name, str) or not name.isidentifier() or name.startswith("_"):
        raise ProgrammerError("Rich-text names must be public Python identifiers")
    if any(type(value) is not bool for value in (encrypted, store_if_blank)):
        raise ProgrammerError("Rich-text declaration options must be booleans")
    if strict_loading is not None and type(strict_loading) is not bool:
        raise ProgrammerError("strict_loading must be a boolean")
    association = f"rich_text_{name}"
    scope = f"with_rich_text_{name}"

    def bind(cls):
        definition = RichTextDefinition(
            encrypted,
            cls.strict_loading_by_default if strict_loading is None else strict_loading,
            store_if_blank,
        )
        inherited = any(
            name in model_for(base).rich_texts
            for base in cls.__mro__[1:]
            if base is not object
        )
        for attribute in (name, association, scope, scope + "_and_embeds"):
            if attribute in dir(cls) and (not inherited or attribute in vars(cls)):
                raise ProgrammerError(
                    f"Rich text {name} conflicts with model attribute {attribute}"
                )
        declarations = model_for(cls)
        if {name, association, scope, scope + "_and_embeds"} & (
            declarations.attachments.keys()
            | declarations.virtual_fields.keys()
            | declarations.associations.keys()
        ):
            raise ProgrammerError(
                f"Rich text {name} conflicts with a model declaration"
            )
        declarations.rich_texts[name] = definition
        setattr(cls, name, property(lambda instance: read(instance, name)))
        setattr(cls, scope, classmethod(lambda owner: owner.includes(association)))
        setattr(
            cls,
            scope + "_and_embeds",
            classmethod(lambda owner: owner.all().with_rich_text_embeds(name)),
        )

    return bind


def _existing(instance, name, *, enforce_strict=True):
    if instance.is_new_record():
        return None
    association = f"rich_text_{name}"
    if (
        enforce_strict
        and model_for(type(instance)).rich_texts[name].strict_loading
        and inspect(instance).attrs[association].loaded_value is NO_VALUE
    ):
        raise StrictLoadingViolationError(
            f"{type(instance).__name__}.{association} must be eager loaded. "
            f"Use with_rich_text_{name}() or with_rich_text_{name}_and_embeds()."
        )
    return object.__getattribute__(instance, association)


def association_value(instance, name):
    row = instance._rich_text_changes.get(name)
    if row is None:
        row = _existing(instance, name)
    if row is not None:
        row._record = instance
    return row


def assign(instance, name, value):
    definition = model_for(type(instance)).rich_texts.get(name)
    if definition is None:
        return False
    from flaskteroids.rich_text.record import RichText

    if isinstance(value, RichText):
        value = value.body
    if value is not None and not isinstance(value, (str, Content)):
        raise TypeError(f"{name} expects an HTML string, Content, RichText, or None")
    content = value if isinstance(value, Content) else Content(value or "")
    if not definition.store_if_blank and content.blank():
        row = instance._rich_text_changes.get(name)
        if row is None:
            row = _existing(instance, name)
        if row is not None:
            row._record = instance
            row.body = content
            row._marked_for_destruction = True
        return True
    read(instance, name).body = content
    return True


def read(instance, name):
    row = association_value(instance, name)
    if row is None:
        row_type = (
            inspect(type(instance)).relationships[f"rich_text_{name}"].mapper.class_
        )
        row = row_type()
        row.name = name
        row.record_type = type(instance).__name__
        row._record = instance
        row.body = None
    else:
        row._record = instance
    return row


def relationship_properties(model, table, registry):
    from flaskteroids.rich_text.record import RichText

    definitions = model_for(model).rich_texts
    if not definitions:
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
    row_type = next(
        (
            mapper.class_
            for mapper in registry.mappers
            if issubclass(mapper.class_, RichText)
        ),
        None,
    )
    if row_type is None:
        row_type = type("RichText", (RichText,), {})
        bind_rules(row_type)
        from flaskteroids.rich_text.embeds import EmbeddedFiles

        row_type.embeds = property(
            lambda row: EmbeddedFiles(row, model_for(type(row)).attachments["embeds"])
        )
        registry.map_imperatively(
            row_type, rich_table, properties={"_body": rich_table.c.body}
        )
    overlaps = {
        f"rich_text_{key}"
        for candidate in model._flaskteroids_model_root._flaskteroids_model_catalog.values()
        for key in model_for(candidate).rich_texts
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
        for name in sorted(definitions)
    }


def validate(instance):
    for name, row in list(instance._rich_text_changes.items()):
        if not row._marked_for_destruction and not row.is_valid():
            instance.errors.append((name, f"{name} contains invalid attachments"))


def persist(instance):
    rows = list(instance._rich_text_changes.items())
    saved = []
    for name, row in rows:
        if row._marked_for_destruction:
            if row.is_persisted():
                attached_storage.destroy(row)
                session.delete(row)
            attributes.set_committed_value(instance, f"rich_text_{name}", None)
        else:
            row._publish()
            session.add(row)
            saved.append(row)
    if rows:
        session.flush()
    for row in saved:
        row._persist_embeds()
        row._changes.clear()
    instance._rich_text_changes.clear()


def discard(instance):
    for row in instance._rich_text_changes.values():
        row._changes.clear()
        row._attachment_changes.clear()
        row._attachment_cache.clear()
        row._marked_for_destruction = False
    instance._rich_text_changes.clear()


def destroy(instance):
    for name in model_for(type(instance)).rich_texts:
        row = _existing(instance, name, enforce_strict=False)
        if row is not None:
            attached_storage.destroy(row)
