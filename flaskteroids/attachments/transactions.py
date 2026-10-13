from dataclasses import dataclass, field

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from flaskteroids.attachments.schema import attachments, blobs

_STATE = "flaskteroids.attachments.transactions"


@dataclass
class UploadBatch:
    uploads: dict = field(default_factory=dict)
    append: bool = False

    def merge(self, other):
        self.uploads.update(other.uploads)
        self.append = other.append

    def close(self):
        for _, close in self.uploads.values():
            close()


def defer_uploads(session, token, uploads, *, append=False):
    batches = _state(session)["uploads"]
    batch = batches.setdefault(token, UploadBatch())
    batch.merge(UploadBatch(uploads, append))


def after_commit(session, action):
    _state(session)["actions"].append(action)


def _state(session):
    transaction = session.get_nested_transaction() or session.get_transaction()
    if transaction is None:
        transaction = session.begin()
    return session.info.setdefault(_STATE, {}).setdefault(
        transaction,
        {"committed": False, "uploads": {}, "attached_keys": set(), "actions": []},
    )


@event.listens_for(Session, "before_commit")
def _prepare_uploads(session):
    state = _state(session)
    keys = {
        key
        for transaction_state in session.info[_STATE].values()
        for batch in transaction_state["uploads"].values()
        for key in batch.uploads
    }
    if keys:
        state["attached_keys"] = set(
            session.scalars(
                select(blobs.c.key)
                .join(attachments, attachments.c.blob_id == blobs.c.id)
                .where(blobs.c.key.in_(keys))
            )
        )


@event.listens_for(Session, "after_commit", insert=True)
def _committed(session):
    state = _state(session)
    state["committed"] = True
    if session.get_nested_transaction() is None:
        for batch in state["uploads"].values():
            for key, (upload, _) in batch.uploads.items():
                if key in state["attached_keys"] or batch.append:
                    upload()


@event.listens_for(Session, "after_transaction_end")
def _finished(session, transaction):
    states = session.info.get(_STATE, {})
    state = states.pop(transaction, None)
    if not state:
        return
    if state["committed"] and transaction.nested:
        parent = states.setdefault(
            transaction.parent,
            {"committed": False, "uploads": {}, "attached_keys": set(), "actions": []},
        )
        parent["attached_keys"] = state["attached_keys"]
        for token, batch in state["uploads"].items():
            parent["uploads"].setdefault(token, UploadBatch()).merge(batch)
        parent["actions"].extend(state["actions"])
        return
    try:
        if state["committed"]:
            for action in state["actions"]:
                action()
    finally:
        for batch in state["uploads"].values():
            batch.close()
