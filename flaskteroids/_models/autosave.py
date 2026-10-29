"""Coordinate framework lifecycles around one native unit-of-work flush."""

from contextlib import ExitStack

from sqlalchemy import inspect
from sqlalchemy.orm.attributes import (
    INCLUDE_PENDING_MUTATIONS,
    NO_VALUE,
    PASSIVE_NO_INITIALIZE,
    get_history,
)

from flaskteroids._models.staging import StagedAttributes
from flaskteroids.callbacks import _HALTED, _callback_chain, queue_after_commit
from flaskteroids.declarations import model_for


def _associated_records(record, relationship):
    value = inspect(record).attrs[relationship.key].loaded_value
    if value is NO_VALUE:
        return get_history(
            record,
            relationship.key,
            passive=PASSIVE_NO_INITIALIZE | INCLUDE_PENDING_MUTATIONS,
        ).added
    if value is None:
        return ()
    return value if relationship.uselist else (value,)


def changed_for_autosave(record, seen=None):
    seen = set() if seen is None else seen
    if id(record) in seen:
        return False
    seen.add(id(record))
    if (
        record.is_new_record()
        or record.changes
        or record.marked_for_destruction()
        or record._attachment_changes
        or record._rich_text_changes
        or inspect(record).modified
    ):
        return True
    for name, definition in model_for(type(record)).associations.items():
        if definition.through is not None or definition.autosave is not True:
            continue
        relationship = inspect(type(record)).relationships[name]
        for related in _associated_records(record, relationship):
            if changed_for_autosave(related, seen):
                return True
    return False


class SaveGraph:
    def __init__(self, root):
        self.records = []
        self.edges = []
        self.destructions = []
        self._seen = set()
        self._visit(root)

    def _visit(self, record):
        if id(record) in self._seen:
            return
        self._seen.add(id(record))
        self.records.append(record)
        state = inspect(record)
        declarations = model_for(type(record)).associations
        for relationship in state.mapper.relationships:
            definition = declarations.get(relationship.key)
            autosave = definition.autosave if definition is not None else None
            if autosave is False or not relationship.cascade.save_update:
                continue
            for index, related in enumerate(_associated_records(record, relationship)):
                if not isinstance(related, StagedAttributes):
                    continue
                path = relationship.key
                if relationship.uselist:
                    path += f"[{index}]"
                if autosave is True and related.marked_for_destruction():
                    self.destructions.append((record, relationship, related))
                elif related.is_new_record() or (
                    autosave is True and changed_for_autosave(related)
                ):
                    self.edges.append((record, path, related))
                    self._visit(related)

    def validate(self):
        validated = {}

        def validate(record, ancestors):
            if id(record) in validated:
                return validated[id(record)]
            ancestors = ancestors | {id(record)}
            children_valid = []

            def validate_associations():
                for owner, path, child in self.edges:
                    if owner is not record or id(child) in ancestors:
                        continue
                    children_valid.append(validate(child, ancestors))
                    for error in child.errors:
                        record.errors.append(
                            (f"{path}.{error.attribute}", error.full_message())
                        )
                    if not children_valid[-1] and not child.errors:
                        record.errors.append((path, "Associated record is invalid"))

            valid = record._validate_record(validate_associations)
            validated[id(record)] = valid and all(children_valid)
            return validated[id(record)]

        return validate(self.records[0], set())

    def run(self, persist, session):
        operations = [
            "create" if record.is_new_record() else "update" for record in self.records
        ]
        with ExitStack() as stack:
            chains = []
            for record, operation in zip(self.records, operations, strict=True):
                for kind, on in (("save", operation), (operation, None)):
                    chain = stack.enter_context(_callback_chain(record, kind, on))
                    if chain is None:
                        return _HALTED
                    chains.append(chain)
            result = persist()
            if result is _HALTED:
                return result
            for record, operation in zip(self.records, operations, strict=True):
                queue_after_commit(record, operation, session)
            for chain in chains:
                chain.result = result
        return result

    def unlink_marked(self, session):
        for owner, relationship, child in self.destructions:
            if not child.is_new_record():
                continue
            if relationship.uselist:
                object.__getattribute__(owner, relationship.key).remove(child)
            else:
                setattr(owner, relationship.key, None)
            if child in session:
                session.expunge(child)

    def destroy_marked(self):
        for owner, relationship, child in self.destructions:
            if child.is_new_record():
                continue
            if not relationship.uselist:
                setattr(owner, relationship.key, None)
            if not child.destroy():
                owner.errors.append(
                    (relationship.key, "Associated destruction was halted")
                )
                return False
            if relationship.uselist:
                object.__getattribute__(owner, relationship.key).remove(child)
        return True
