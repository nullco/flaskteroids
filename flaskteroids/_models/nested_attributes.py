"""Opt-in nested assignment, using the association's own identity and storage."""

from collections.abc import Mapping
from dataclasses import replace

from sqlalchemy import inspect

from flaskteroids.declarations import NestedAttributesDefinition, model_for
from flaskteroids.exceptions import ProgrammerError, RecordNotFoundException
from flaskteroids.rules import declaration


class TooManyRecords(ValueError):
    """A nested collection exceeds its declared input limit."""


@declaration
def accepts_nested_attributes_for(
    *names, allow_destroy=False, reject_if=None, limit=None, update_only=False
):
    if not names or any(
        not isinstance(name, str) or not name.isidentifier() for name in names
    ):
        raise ProgrammerError("Specify nested association names as Python identifiers.")
    if type(allow_destroy) is not bool or type(update_only) is not bool:
        raise ProgrammerError("allow_destroy and update_only must be booleans.")
    if (
        reject_if is not None
        and not isinstance(reject_if, str)
        and not callable(reject_if)
    ):
        raise ProgrammerError(
            "reject_if must be 'all_blank', a method name, or callable."
        )
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ProgrammerError("Nested attribute limit must be a nonnegative integer.")

    def bind(cls):
        if (
            isinstance(reject_if, str)
            and reject_if != "all_blank"
            and not callable(getattr(cls, reject_if, None))
        ):
            raise ProgrammerError(f"Unknown nested rejection method {reject_if!r}.")
        definition = model_for(cls)
        for name in names:
            if name not in definition.associations:
                raise ProgrammerError(
                    f"Declare association {cls.__name__}.{name} first."
                )
            if definition.associations[name].through is not None:
                raise ProgrammerError(
                    "Declare nested attributes on the join association, "
                    "not the through collection."
                )
            writer = f"{name}_attributes"
            if any(writer in vars(base) for base in cls.__mro__):
                raise ProgrammerError(
                    f"Nested writer {cls.__name__}.{writer} conflicts with model API."
                )
            definition.nested_attributes[name] = NestedAttributesDefinition(
                allow_destroy, reject_if, limit, update_only
            )
            definition.associations[name] = replace(
                definition.associations[name], autosave=True
            )

    return bind


def association_for_writer(record, name):
    if name.endswith("_attributes"):
        association = name.removesuffix("_attributes")
        if association in model_for(type(record)).nested_attributes:
            return association
    return None


def _blank(value):
    if value is None or value is False:
        return True
    if isinstance(value, str):
        return not value.strip()
    return isinstance(value, (list, dict)) and not value


def _destroy_requested(attributes):
    value = attributes.get("_destroy")
    return value is not None and value not in (
        False,
        0,
        "",
        "0",
        "false",
        "False",
        "FALSE",
        "off",
        "OFF",
    )


def _rejected(owner, attributes, options):
    if options.allow_destroy and _destroy_requested(attributes):
        return False
    reject = options.reject_if
    if reject == "all_blank":
        return all(
            key == "_destroy" or _blank(value) for key, value in attributes.items()
        )
    if isinstance(reject, str):
        return bool(getattr(owner, reject)(attributes))
    return bool(reject(attributes)) if reject is not None else False


def _attributes(value):
    if not isinstance(value, Mapping):
        raise TypeError("Nested attributes must be a mapping.")
    if any(not isinstance(key, str) for key in value):
        raise TypeError("Nested attribute names must be strings.")
    return dict(value)


def assign(record, name, value):
    definition = model_for(type(record))
    association = definition.associations[name]
    options = definition.nested_attributes[name]
    relationship = inspect(type(record)).relationships[name]
    if (
        len(relationship.mapper.primary_key) != 1
        or relationship.mapper.primary_key[0].key != "id"
    ):
        raise ProgrammerError("Nested attributes require an id primary key.")
    collection = association.kind == "has_many"
    if collection:
        if isinstance(value, Mapping):
            values = [value] if "id" in value else list(value.values())
        elif isinstance(value, list):
            values = value
        else:
            raise TypeError("Nested collection attributes must be a list or mapping.")
        if options.limit is not None and len(values) > options.limit:
            raise TooManyRecords(f"{name} accepts at most {options.limit} records.")
        values = [_attributes(item) for item in values]
        targets = list(getattr(record, name))
    else:
        values = [_attributes(value)]
        target = getattr(record, name)
        targets = [target] if target is not None else []

    for attributes in values:
        identifier = attributes.get("id")
        has_id = not _blank(identifier)
        target = next(
            (entry for entry in targets if has_id and str(entry.id) == str(identifier)),
            None,
        )
        if not collection and options.update_only and targets:
            target = targets[0]
        if has_id and target is None:
            raise RecordNotFoundException(
                f"{relationship.mapper.class_.__name__} {identifier} does not belong to {type(record).__name__}.{name}."
            )
        if target is None and options.allow_destroy and _destroy_requested(attributes):
            continue
        if _rejected(record, attributes, options):
            continue
        assignable = {
            key: item
            for key, item in attributes.items()
            if key not in {"id", "_destroy"}
        }
        # The owning association, not submitted foreign keys, determines ownership.
        if association.kind != "belongs_to":
            assignable.pop(association.foreign_key, None)
            if relationship.back_populates:
                assignable.pop(relationship.back_populates, None)
        if target is None:
            if not collection and targets and targets[0].is_new_record():
                target = targets[0]
                target.assign_attributes(**assignable)
            elif collection:
                target = getattr(record, name).new(**assignable)
                targets.append(target)
            else:
                target = relationship.mapper.class_.new(**assignable)
                setattr(record, name, target)
                targets = [target]
        else:
            target.assign_attributes(**assignable)
        if options.allow_destroy and _destroy_requested(attributes):
            target.mark_for_destruction()
