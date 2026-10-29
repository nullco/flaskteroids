"""Association target loading, separate from ORM identity and join persistence."""

from dataclasses import dataclass, field
from weakref import WeakValueDictionary

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import (
    INCLUDE_PENDING_MUTATIONS,
    NO_VALUE,
    PASSIVE_NO_INITIALIZE,
    get_history,
)

from flaskteroids.declarations import model_for

_SESSION_OWNERS = "flaskteroids.association_targets"


@dataclass
class AssociationTargets:
    records: list = field(default_factory=list)
    loaded: bool = False

    def load(self, records):
        self.records = list(records)
        self.loaded = True


def targets_for(owner, name):
    states = vars(owner).setdefault("_association_targets", {})
    if name not in states:
        states[name] = AssociationTargets()
    state = states[name]
    db_session = inspect(owner).session
    if db_session is not None:
        _track_owner(db_session, owner)
    return state


def reset_targets(owner):
    vars(owner).get("_association_targets", {}).clear()


def _track_owner(db_session, owner):
    owners = db_session.info.get(_SESSION_OWNERS)
    if owners is None:
        owners = db_session.info[_SESSION_OWNERS] = WeakValueDictionary()
    if owners.get(id(owner)) is not owner:
        owners[id(owner)] = owner


@event.listens_for(Session, "after_attach")
def _attached(db_session, owner):
    if vars(owner).get("_association_targets"):
        _track_owner(db_session, owner)


@event.listens_for(Session, "after_soft_rollback")
def _rolled_back(db_session, previous_transaction):
    # Include owners made transient by rollback, not just the current identity map.
    for owner in list(db_session.info.get(_SESSION_OWNERS, {}).values()):
        reset_targets(owner)


def pending_joins(owner, definition):
    value = inspect(owner).attrs[definition.through].loaded_value
    if value is NO_VALUE:
        value = get_history(
            owner,
            definition.through,
            passive=PASSIVE_NO_INITIALIZE | INCLUDE_PENDING_MUTATIONS,
        ).added
    return [join for join in value if join.is_new_record()]


def pending_targets(owner, definition):
    records = []
    for join in pending_joins(owner, definition):
        record = inspect(join).attrs[definition.source].loaded_value
        if record is not NO_VALUE and record is not None:
            records.append(record)
    return records


def include_options(model, paths):
    options, plans = [], {}
    for path in paths:
        if (
            not isinstance(path, str)
            or not path
            or any(not part for part in path.split("."))
        ):
            raise ValueError("includes() expects nonempty dotted relationship paths")
        current, option, prefix, through = model, None, [], False
        names = path.split(".")
        for index, name in enumerate(names):
            definition = model_for(current).associations.get(name)
            if definition is not None and definition.through is not None:
                if not through:
                    key = (tuple(prefix), name)
                    tails = plans.setdefault(key, [])
                    tail = ".".join(names[index + 1 :])
                    if tail and tail not in tails:
                        tails.append(tail)
                    through = True
                current = current._flaskteroids_model_root._flaskteroids_model_catalog[
                    definition.target
                ]
                continue
            relationship = inspect(current).relationships.get(name)
            if relationship is None:
                raise AttributeError(f"Unknown relationship {current.__name__}.{name}")
            if not through:
                attribute = getattr(current, name)
                option = (
                    selectinload(attribute)
                    if option is None
                    else option.selectinload(attribute)
                )
                prefix.append(name)
            current = relationship.mapper.class_
        if option is not None:
            options.append(option)
    return options, {key: tuple(tails) for key, tails in plans.items()}


def _unique(records):
    return list({id(record): record for record in records}.values())


def _batches(identities):
    identities = list(identities)
    for start in range(0, len(identities), 500):
        yield identities[start : start + 500]


def preload_associations(records, plans, query_factory):
    for (prefix, name), tails in plans.items():
        owners = _unique(records)
        for part in prefix:
            related = []
            for owner in owners:
                relationship = inspect(type(owner)).relationships[part]
                value = object.__getattribute__(owner, part)
                if relationship.uselist:
                    related.extend(value)
                elif value is not None:
                    related.append(value)
            owners = _unique(related)
        if owners:
            load_through(owners, name, tails, query_factory)


def _native_loaded(records, paths):
    for path in paths:
        owners = records
        for name in path.split("."):
            if not owners:
                break
            definition = model_for(type(owners[0])).associations.get(name)
            if definition is not None and definition.through is not None:
                break
            related = []
            for owner in owners:
                relationship = inspect(type(owner)).relationships[name]
                value = inspect(owner).attrs[name].loaded_value
                if value is NO_VALUE:
                    if owner.is_persisted():
                        return False
                elif relationship.uselist:
                    related.extend(value)
                elif value is not None:
                    related.append(value)
            owners = _unique(related)
    return True


def load_through(owners, name, tails, query_factory):
    owners = _unique(owners)
    owner_model = type(owners[0])
    definition = model_for(owner_model).associations[name]
    relationship = inspect(owner_model).relationships[definition.through]
    join_model = relationship.mapper.class_
    source = getattr(join_model, definition.source)
    target_model = inspect(join_model).relationships[definition.source].mapper.class_
    _, owner_key = relationship.local_remote_pairs[0]
    unloaded = [owner for owner in owners if not targets_for(owner, name).loaded]
    persisted = {
        inspect(owner).identity[0]: owner for owner in unloaded if owner.is_persisted()
    }
    groups = {identifier: [] for identifier in persisted}
    for batch in _batches(persisted):
        query = query_factory(target_model).includes(*tails)
        query.statement = (
            query.statement.join_from(join_model, source)
            .add_columns(owner_key)
            .where(owner_key.in_(batch))
        )
        rows = query._session().execute(query.statement).all()
        query._preload_records([row[0] for row in rows])
        for record, identifier in rows:
            groups[identifier].append(record)
    extras = []
    for owner in unloaded:
        identity = inspect(owner).identity
        records = groups.get(identity[0], []) if identity is not None else []
        pending = pending_targets(owner, definition)
        targets_for(owner, name).load([*records, *pending])
        if tails:
            extras.extend(pending)
    if not tails:
        return

    # Nested includes also apply to cached targets and unsaved additions.
    unloaded_ids = {id(owner) for owner in unloaded}
    extras.extend(
        record
        for owner in owners
        if id(owner) not in unloaded_ids
        for record in targets_for(owner, name).records
    )
    if extras:
        records = _unique(extras)
        identities = [
            inspect(record).identity[0] for record in records if record.is_persisted()
        ]
        query = query_factory(target_model).includes(*tails)
        if identities and not _native_loaded(records, tails):
            primary_key = inspect(target_model).primary_key[0]
            for batch in _batches(identities):
                list(query.where(primary_key.in_(batch)))
        preload_associations(records, query._through_preloads, query_factory)
