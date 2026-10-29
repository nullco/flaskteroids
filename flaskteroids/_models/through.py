"""Cached through targets, with writes delegated to ordinary join models."""

from dataclasses import replace

from sqlalchemy import false, inspect
from sqlalchemy.orm import with_parent
from sqlalchemy.orm.attributes import NO_VALUE, set_committed_value

from flaskteroids._models.association_loading import (
    load_through,
    pending_joins,
    pending_targets,
    targets_for,
)
from flaskteroids._models.associations import AssociationCollection
from flaskteroids._models.query import ModelQuery
from flaskteroids.db import session, transactional
from flaskteroids.declarations import model_for
from flaskteroids.exceptions import ProgrammerError, RecordInvalid
from flaskteroids.inflector import inflector


def prepare_through_associations(cls, catalog):
    declarations = model_for(cls).associations
    for name, definition in list(declarations.items()):
        if definition.through is None:
            continue
        through = declarations.get(definition.through)
        if through is None or through.kind != "has_many" or through.through is not None:
            raise ProgrammerError(
                f"{cls.__name__}.{name} requires a direct has_many association "
                f"named {definition.through!r}."
            )
        if through.autosave is False:
            raise ProgrammerError("A through association requires autosaved new joins.")
        join = catalog[through.target]
        sources = model_for(join).associations
        candidates = list(dict.fromkeys((inflector.singularize(name), name)))
        matches = [candidate for candidate in candidates if candidate in sources]
        source_name = definition.source
        if source_name is None:
            if len(matches) != 1:
                raise ProgrammerError(
                    f"Specify source for {cls.__name__}.{name}; expected one "
                    f"association on {join.__name__} matching {candidates}."
                )
            source_name = matches[0]
        source = sources.get(source_name)
        if source is None or source.kind != "belongs_to" or source.through is not None:
            raise ProgrammerError(
                f"{cls.__name__}.{name} requires a direct belongs_to source "
                f"{join.__name__}.{source_name}."
            )
        if source.autosave is False:
            raise ProgrammerError("A through source must save new associated targets.")
        declarations[name] = replace(
            definition, target=source.target, source=source_name
        )


class ThroughQuery(ModelQuery):
    def __init__(self, owner, name):
        self.owner = owner
        self.name = name
        definition = model_for(type(owner)).associations[name]
        self.through = definition.through
        self.source = definition.source
        relationship = inspect(type(owner)).relationships[self.through]
        self.join_model = relationship.mapper.class_
        target = inspect(self.join_model).relationships[self.source].mapper.class_
        super().__init__(target)
        # Joining via the instrumented source handles custom foreign/primary keys.
        self.statement = self.statement.join_from(
            self.join_model, getattr(self.join_model, self.source)
        ).where(
            false()
            if owner.is_new_record()
            else with_parent(owner, getattr(type(owner), self.through))
        )

    def new(self, **attributes):
        record = super().new(**attributes)
        ThroughCollection(self.owner, self.name).build_join(record)
        return record

    def create(self, **attributes):
        if not self.owner.is_persisted():
            raise ProgrammerError("Save the parent before creating associated records.")
        record = self._model_cls.new(**(self._creation_attributes | attributes))
        ThroughCollection(self.owner, self.name).create_record(record)
        return record

    def _load_records(self):
        # Repeated targets represent distinct join records, just as in Rails.
        return self._preload_records(
            self._session().execute(self.statement).scalars().all()
        )


class ThroughCollection(AssociationCollection):
    def __init__(self, owner, name):
        super().__init__(owner, name)
        self.definition = model_for(type(owner)).associations[name]
        self.through = self.definition.through
        self.source = self.definition.source
        self.relationship = inspect(type(owner)).relationships[self.through]
        self.join_model = self.relationship.mapper.class_
        self.target_model = (
            inspect(self.join_model).relationships[self.source].mapper.class_
        )

    @property
    def _targets(self):
        return targets_for(self.owner, self.name)

    def _joins(self):
        return getattr(self.owner, self.through)

    def _collection(self):
        if not self._targets.loaded:
            load_through([self.owner], self.name, (), ModelQuery)
        return self._targets.records

    def _loaded_collection(self):
        state = self._targets
        return state.records if state.loaded else NO_VALUE

    def _pending_records(self):
        return pending_joins(self.owner, self.definition)

    def _pending_count(self):
        return len(pending_targets(self.owner, self.definition))

    def all(self) -> ThroughQuery:
        return ThroughQuery(self.owner, self.name)

    def _check_type(self, record):
        if not isinstance(record, self.target_model):
            raise TypeError(
                f"{type(self.owner).__name__}.{self.name} expects "
                f"{self.target_model.__name__} records."
            )

    def build_join(self, record, *, add_to_target=True):
        self._check_type(record)
        joins = self._joins()
        # Load the native collection before linking, retaining unsaved joins even
        # when the join's owner association has no inverse declaration.
        list(joins)
        join = joins.new(**{self.source: record})
        if join not in joins:
            joins.append(join)
        if add_to_target and self._targets.loaded:
            self._targets.records.append(record)
        return join

    def _unlink(self, join):
        target = getattr(join, self.source)
        inverse = inspect(self.join_model).relationships[self.source].back_populates
        self._joins().remove(join)
        if inverse and target is not None:
            relationship = inspect(type(target)).relationships[inverse]
            if relationship.uselist:
                collection = getattr(target, inverse)
                if join in collection:
                    collection.remove(join)
            else:
                setattr(target, inverse, None)
        else:
            setattr(join, self.source, None)
        if join.is_new_record() and join in session:
            session.expunge(join)

    def _save_target(self, record):
        if record.is_new_record() or record.changes:
            if not record.save():
                raise RecordInvalid(record)

    def _save_join(self, record):
        join = self.build_join(record, add_to_target=False)
        try:
            if not join.save():
                raise RecordInvalid(join)
        except Exception as error:
            if session.is_active:
                self._unlink(join)
                if isinstance(error, RecordInvalid):
                    # Keep the rejected record inspectable without leaving it
                    # in inverse collections for an unrelated later save.
                    set_committed_value(join, self.source, record)
                    if inverse := self.relationship.back_populates:
                        set_committed_value(join, inverse, self.owner)
            raise
        return join

    @transactional
    def create_record(self, record):
        # create returns invalid target input; invalid join records raise, since
        # silently returning a saved but unassociated target would lose errors.
        if not record.save():
            return
        self._save_join(record)
        if self._targets.loaded:
            self._targets.records.append(record)

    def append(self, record):
        self._insert(None, record)

    def insert(self, index, record):
        self._collection()
        self._insert(index, record)

    def _insert(self, index, record):
        self._check_type(record)
        if self.owner.is_new_record():
            join = self.build_join(record, add_to_target=False)
            self._insert_target(index, record, join)
        else:
            self._insert_saved(index, record)

    @transactional
    def _insert_saved(self, index, record):
        self._save_target(record)
        self._insert_target(index, record, self._save_join(record))

    def _insert_target(self, index, record, join):
        if index is not None:
            self._move_join(index, join)
        if self._targets.loaded:
            if index is None:
                self._targets.records.append(record)
            else:
                self._targets.records.insert(index, record)

    def _move_join(self, index, join):
        joins = self._joins()
        joins.remove(join)
        joins.insert(index, join)

    def replace(self, records):
        if self.owner.is_new_record():
            self._replace(records)
        else:
            self._replace_saved(records)

    @transactional
    def _replace_saved(self, records):
        self._replace(records)

    def _replace(self, records):
        records = list(records)
        for record in records:
            self._check_type(record)
        remaining = [join for join in self._joins() if not inspect(join).was_deleted]
        additions = []
        desired = []
        for record in records:
            match = next(
                (join for join in remaining if getattr(join, self.source) is record),
                None,
            )
            if match is not None:
                remaining.remove(match)
                desired.append(match)
            else:
                additions.append(record)
                desired.append(None)
        built = []
        try:
            for record in additions:
                if self.owner.is_persisted():
                    self._save_target(record)
                    built.append(self._save_join(record))
                else:
                    built.append(self.build_join(record, add_to_target=False))
            for join in remaining:
                if join.is_persisted():
                    session.delete(join)
                self._unlink(join)
            if self.owner.is_persisted():
                session.flush()
        except Exception:
            if session.is_active:
                for join in built:
                    if join in self._joins():
                        self._unlink(join)
            raise
        # Preserve requested order in native join storage; persisted order still
        # follows the database unless an explicit query order is supplied.
        pending = iter(built)
        ordered = [join if join is not None else next(pending) for join in desired]
        self._joins()[:] = ordered
        self._targets.load(records)

    def __setitem__(self, index, value):
        records = list(self._collection())
        records[index] = value
        self.replace(records)

    def __delitem__(self, index):
        records = list(self._collection())
        del records[index]
        self.replace(records)

    def remove(self, value):
        records = self._collection()
        if value not in records:
            raise ValueError("Record is not in this association.")
        # Rails deletes all matching joins, without destroying the targets.
        self.replace([record for record in records if record is not value])

    def clear(self):
        self.replace([])

    def extend(self, values):
        self.replace([*self._collection(), *values])

    def reverse(self):
        self._collection().reverse()
