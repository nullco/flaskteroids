"""Record DOM identities, deliberately independent of route parameters."""

from flaskteroids.inflector import inflector


def dom_class(record_or_class, prefix=None):
    """Return the underscored model name, optionally prefixed."""
    if record_or_class is None or (
        not isinstance(record_or_class, type)
        and not callable(getattr(record_or_class, "to_key", None))
    ):
        raise ValueError("Expected a model class or a record with to_key()")
    cls = (
        record_or_class if isinstance(record_or_class, type) else type(record_or_class)
    )
    name = inflector.underscore(cls.__name__)
    return f"{prefix}_{name}" if prefix else name


def dom_id(record_or_class, prefix=None):
    """Return prefix_model_key, or new_model when the record has no key."""
    name = dom_class(record_or_class)
    key = None if isinstance(record_or_class, type) else record_or_class.to_key()
    if key and all(value is not None for value in key):
        identifier = "_".join(str(value) for value in key)
        return f"{dom_class(record_or_class, prefix)}_{identifier}"
    return f"{prefix or 'new'}_{name}"
