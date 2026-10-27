import logging
from inspect import getattr_static
from weakref import WeakKeyDictionary

from sqlalchemy import event as sa_event
from sqlalchemy.orm import Session as _SQLASession
from werkzeug.local import LocalProxy

from flaskteroids.declarations import model_for
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.rules import declaration

_logger = logging.getLogger(__name__)

# Sentinel returned by run_callbacks when the chain is halted.
_HALTED = object()
_COMMIT_CALLBACKS = "flaskteroids.commit_callbacks"

# Callback names that accept the <on> option, and the values each accepts.
# <on> applies to callbacks that fire in more than one context (validation,
# save) or after a transaction (commit/rollback).
ON_VALUES = {
    "before_validation": {"create", "update"},
    "after_validation": {"create", "update"},
    "before_save": {"create", "update"},
    "around_save": {"create", "update"},
    "after_save": {"create", "update"},
    "after_commit": {"create", "update", "destroy"},
    "after_rollback": {"create", "update", "destroy"},
}

# Maps a callback "kind" to its (before, around, after) callback names.
# None means the kind has no callbacks for that position.
KIND_PARTS = {
    "initialize": (None, None, "after_initialize"),
    "find": (None, None, "after_find"),
    "validation": ("before_validation", None, "after_validation"),
    "save": ("before_save", "around_save", "after_save"),
    "create": ("before_create", "around_create", "after_create"),
    "update": ("before_update", "around_update", "after_update"),
    "destroy": ("before_destroy", "around_destroy", "after_destroy"),
    "commit": (None, None, "after_commit"),
    "rollback": (None, None, "after_rollback"),
}


def _conditions(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _normalize_on(name, on):
    if on is None:
        return None
    allowed = ON_VALUES.get(name)
    if allowed is None:
        raise ProgrammerError(
            f"The <on> option is not supported for <{name}> callbacks. "
            f"It is available on: {sorted(ON_VALUES)}."
        )
    values = list(on) if isinstance(on, (list, tuple, set)) else [on]
    for value in values:
        if value not in allowed:
            raise ProgrammerError(
                f"Invalid <on> value for <{name}>: {value!r}. "
                f"Expected one of {sorted(allowed)}."
            )
    return values


def _evaluate(condition, instance):
    if callable(condition):
        return bool(condition(instance))
    return bool(getattr(instance, condition)())


class Callback:
    def __init__(self, method_name, *, when=None, unless=None, on=None, prepend=False):
        self.method_name = method_name
        self.when = _conditions(when)
        self.unless = _conditions(unless)
        self.on = on
        self.prepend = prepend

    def applies(self, instance, operation):
        if self.on is not None and operation not in self.on:
            return False
        if any(not _evaluate(condition, instance) for condition in self.when):
            return False
        return not any(_evaluate(condition, instance) for condition in self.unless)

    def call(self, instance):
        return getattr(instance, self.method_name)()

    def __repr__(self):
        return f"<Callback {self.method_name} on={self.on}>"


def _register_callback(
    cls, name, method_name, *, when=None, unless=None, on=None, prepend=False
):
    if getattr_static(cls, method_name, None) is None:
        raise ProgrammerError(
            f"Callback method <{method_name}> not found on <{cls.__name__}>. "
            "Make sure the method is defined on the model before registering the callback."
        )
    on = _normalize_on(name, on)

    chain = model_for(cls).callbacks.setdefault(name, [])
    callback = Callback(method_name, when=when, unless=unless, on=on, prepend=prepend)
    if prepend:
        chain.insert(0, callback)
    else:
        chain.append(callback)
    _logger.debug(f"{name}: registered <{method_name}> on <{cls.__name__}>")


def _make_callback(name):
    def decorator(method_name, *, when=None, unless=None, on=None, prepend=False):
        def bind(cls):
            _register_callback(
                cls, name, method_name, when=when, unless=unless, on=on, prepend=prepend
            )

        return bind

    decorator.__name__ = name
    return declaration(decorator)


before_validation = _make_callback("before_validation")
after_validation = _make_callback("after_validation")
before_save = _make_callback("before_save")
around_save = _make_callback("around_save")
after_save = _make_callback("after_save")
before_create = _make_callback("before_create")
around_create = _make_callback("around_create")
after_create = _make_callback("after_create")
before_update = _make_callback("before_update")
around_update = _make_callback("around_update")
after_update = _make_callback("after_update")
before_destroy = _make_callback("before_destroy")
around_destroy = _make_callback("around_destroy")
after_destroy = _make_callback("after_destroy")
after_commit = _make_callback("after_commit")
after_rollback = _make_callback("after_rollback")
after_initialize = _make_callback("after_initialize")
after_find = _make_callback("after_find")


def run_callbacks(instance, kind, operation, body, *args, **kwargs):
    """
    Run the callback chain for ``kind`` around ``body``.

    Before callbacks run in registration order, around callbacks wrap the body
    (generator-based, like the controller around_action pattern), and after
    callbacks run in reverse registration order (LIFO).

    Returns ``_HALTED`` if a before callback returns ``False`` or an around
    callback fails to yield; otherwise returns the body's return value.
    """
    chains = model_for(instance.__class__).callbacks
    before_name, around_name, after_name = KIND_PARTS[kind]

    before = chains.get(before_name, []) if before_name else []
    around = chains.get(around_name, []) if around_name else []
    after = chains.get(after_name, []) if after_name else []

    for callback in before:
        if not callback.applies(instance, operation):
            continue
        result = callback.call(instance)
        if result is False:
            _logger.debug(f"{before_name} <{callback.method_name}> halted {instance!r}")
            return _HALTED

    generators = []
    for callback in around:
        if not callback.applies(instance, operation):
            continue
        gen = callback.call(instance)
        try:
            next(gen)
        except StopIteration:
            _logger.debug(f"{around_name} <{callback.method_name}> halted {instance!r}")
            _finalize_around(generators)
            return _HALTED
        generators.append(gen)

    try:
        result = body(*args, **kwargs)
    except BaseException:
        _finalize_around(generators)
        raise

    _finalize_around(generators)
    if result is _HALTED:
        return _HALTED

    for callback in reversed(after):
        if not callback.applies(instance, operation):
            continue
        callback.call(instance)

    return result


def _finalize_around(generators):
    for gen in reversed(generators):
        try:
            next(gen)
        except StopIteration:
            pass


# --- after_commit / after_rollback transaction hooks ---

_pending = WeakKeyDictionary()
_committed_transactions = WeakKeyDictionary()


def _resolve_session(session_obj):
    if isinstance(session_obj, LocalProxy):
        return session_obj._get_current_object()
    return session_obj


def queue_after_commit(instance, operation, session_obj):
    sess = _resolve_session(session_obj)
    # One entry per record per transaction (latest operation wins), so saving
    # the same record multiple times in one transaction fires once.
    transaction = sess.get_nested_transaction() or sess.get_transaction()
    entries = _pending.setdefault(sess, {}).setdefault(transaction, {})
    entries[id(instance)] = (instance, operation, instance.saved_changes)


@sa_event.listens_for(_SQLASession, "before_commit")
def _prepare_commit(session_obj):
    if session_obj.get_nested_transaction() is not None:
        return
    transaction = session_obj.get_transaction()
    for instance, operation, _ in (
        _pending.get(session_obj, {}).get(transaction, {}).values()
    ):
        if operation != "destroy":
            instance._prepare_commit()


@sa_event.listens_for(_SQLASession, "after_commit")
def _on_session_commit(session_obj):
    transaction = session_obj.get_nested_transaction() or session_obj.get_transaction()
    _committed_transactions.setdefault(session_obj, set()).add(transaction)


@sa_event.listens_for(_SQLASession, "after_rollback")
def _on_session_rollback(session_obj):
    transaction = session_obj.get_nested_transaction() or session_obj.get_transaction()
    entries = _pending.get(session_obj, {}).pop(transaction, {})
    for instance, operation, _ in entries.values():
        instance._saved_changes = {}
        run_callbacks(instance, "rollback", operation, lambda: None)


@sa_event.listens_for(_SQLASession, "after_transaction_end")
def _on_transaction_end(session_obj, transaction):
    entries = _pending.get(session_obj, {}).pop(transaction, {})
    committed = _committed_transactions.get(session_obj, set())
    if transaction not in committed:
        return
    committed.remove(transaction)
    if transaction.nested:
        parent = _pending.setdefault(session_obj, {}).setdefault(transaction.parent, {})
        parent.update(entries)
        return
    for instance, _, changes in entries.values():
        instance._saved_changes = changes

    # SQLAlchemy closes the transaction before this event, but a `with begin()`
    # context still points at that closed boundary until __exit__ returns. Suspend
    # only that context guard so callbacks can use the same session/identity map.
    context = session_obj._trans_context_manager
    if context is not None and not context.is_active:
        session_obj._trans_context_manager = None
    previous = session_obj.info.get(_COMMIT_CALLBACKS, False)
    session_obj.info[_COMMIT_CALLBACKS] = True
    try:
        for instance, operation, _ in entries.values():
            run_callbacks(instance, "commit", operation, lambda: None)
    finally:
        if previous:
            session_obj.info[_COMMIT_CALLBACKS] = previous
        else:
            session_obj.info.pop(_COMMIT_CALLBACKS, None)
        session_obj._trans_context_manager = context
