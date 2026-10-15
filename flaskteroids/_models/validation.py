from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable, Sequence
from functools import partial
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

from flaskteroids.declarations import model_for

if TYPE_CHECKING:
    from flaskteroids.model import Model

# Keep the historical logger configuration path after extraction.
_logger = logging.getLogger("flaskteroids.model")


class Error:
    def __init__(self, args: Sequence[str]) -> None:
        self._args = args

    def full_message(self) -> str:
        return self._args[-1]

    def __repr__(self):
        return f"<ModelError:{hex(id(self))} {{args={self._args}}}>"


class Errors:
    def __init__(self) -> None:
        self._errors: list[Error] = []

    def append(self, error: Sequence[str]) -> None:
        self._errors.append(Error(error))

    def extend(self, errors: Iterable[Sequence[str]]) -> None:
        self._errors.extend([Error(e) for e in errors])

    def full_messages(self) -> list[str]:
        return [e.full_message() for e in self._errors]

    def __json__(self) -> list[str]:
        return self.full_messages()

    @property
    def count(self) -> int:
        return len(self._errors)

    def __bool__(self) -> bool:
        return bool(self._errors)

    def __repr__(self):
        return repr([e for e in self._errors])

    def __len__(self) -> int:
        return len(self._errors)


class PresenceConfig(TypedDict):
    message: NotRequired[str]


class LengthConfig(TypedDict):
    minimum: NotRequired[int]
    maximum: NotRequired[int]


class NumericalityConfig(TypedDict, total=False):
    only_integer: bool
    allow_nil: bool
    message: str


class ComparisonConfig(TypedDict):
    greater_than: NotRequired[Any]
    less_than: NotRequired[Any]
    less_than_or_equal_to: NotRequired[Any]
    greater_than_or_equal_to: NotRequired[Any]
    equal_to: NotRequired[Any]
    other_than: NotRequired[Any]


def validates(
    field: str,
    *,
    presence: None | PresenceConfig | bool = None,
    length: None | LengthConfig = None,
    confirmation: None | bool = None,
    comparison: None | ComparisonConfig = None,
    numericality: None | NumericalityConfig | bool = None,
) -> Callable[[type[Model]], None]:
    options = {
        "presence": {"config": presence, "validator": _validate_presence},
        "length": {"config": length, "validator": _validate_length},
        "confirmation": {"config": confirmation, "validator": _validate_confirmation},
        "comparison": {"config": comparison, "validator": _validate_comparison},
        "numericality": {"config": numericality, "validator": _validate_numericality},
    }
    options = {k: v for k, v in options.items() if v["config"] is not None}

    def bind(model_cls: type[Model]) -> None:
        definition = model_for(model_cls)
        for value in options.values():
            definition.validators.append(
                partial(value["validator"], field=field, config=value["config"])
            )
        if "confirmation" in options:
            definition.virtual_fields[f"{field}_confirmation"] = {}

    return bind


def _validate_presence(
    *, instance: Model, field: str, config: PresenceConfig | bool | None
) -> list[tuple[str, str]]:
    if not config:
        return []
    if isinstance(config, bool):
        config = {"message": f"Field {field} is blank"}

    errors = []
    value = getattr(instance, field)
    if value is None or (isinstance(value, str) and not value.strip()):
        errors.append((f"{field}.presence", config["message"]))
    return errors


def _validate_length(
    *, instance: Model, field: str, config: LengthConfig | None
) -> list[tuple[str, str]]:
    if not config:
        return []
    errors = []
    value = getattr(instance, field)

    if value is not None:
        minimum = config.get("minimum")
        maximum = config.get("maximum")
        if minimum is not None and len(value) < minimum:
            errors.append((f"{field}.length", f"Field {field} is lower than {minimum}"))
        if maximum is not None and len(value) > maximum:
            errors.append(
                (f"{field}.length", f"Field {field} is higher than {maximum}")
            )
    return errors


def _validate_confirmation(
    *, instance: Model, field: str, config: None | bool
) -> list[tuple[str, str]]:
    if not config:
        return []
    errors = []
    value = getattr(instance, field)
    if value is not None:
        confirmation_field = f"{field}_confirmation"
        if confirmation_field in instance._virtual_fields:
            confirmation_value = instance._virtual_fields.get(confirmation_field)
            if confirmation_value != value:
                errors.append(
                    (f"{field}.confirmation", f"Field {field} values do not match")
                )
    return errors


def _validate_numericality(*, instance, field, config):
    if not config:
        return []
    options = {} if config is True else config
    value = instance.read_attribute_before_type_cast(field)
    if value is None and options.get("allow_nil"):
        return []
    valid = not isinstance(value, bool) and value is not None
    if options.get("only_integer"):
        valid = valid and re.fullmatch(r"[+-]?\d+", str(value)) is not None
    else:
        try:
            float(value)
        except (ValueError, TypeError):
            valid = False
    if valid:
        return []
    message = options.get("message", f"Field {field} is not a number")
    return [(f"{field}.numericality", message)]


def _resolve_comparison_value(instance: Model, compare_value: Any) -> Any:
    if callable(compare_value):
        return compare_value()
    if isinstance(compare_value, str):
        return getattr(instance, compare_value, None)
    return compare_value


def _validate_comparison(
    *, instance: Model, field: str, config: ComparisonConfig | None
) -> list[tuple[str, str]]:
    if not config:
        return []
    errors = []
    value = getattr(instance, field)
    if value is None:
        return errors

    comparisons = {
        "greater_than": (lambda a, b: a > b, "must be greater than"),
        "less_than": (lambda a, b: a < b, "must be less than"),
        "greater_than_or_equal_to": (
            lambda a, b: a >= b,
            "must be greater than or equal to",
        ),
        "less_than_or_equal_to": (lambda a, b: a <= b, "must be less than or equal to"),
        "equal_to": (lambda a, b: a == b, "must be equal to"),
        "other_than": (lambda a, b: a != b, "must be other than"),
    }

    for comparator, raw_compare_value in config.items():
        if comparator not in comparisons:
            continue

        compare_value = _resolve_comparison_value(instance, raw_compare_value)
        if compare_value is None:
            continue

        check_fn, message = comparisons[comparator]
        try:
            if not check_fn(value, compare_value):
                _logger.debug(
                    f"Comparison failed: instance={instance!r}, field={field}, value={value}, comparator={comparator}, compare_value={compare_value}"
                )
                errors.append(
                    (f"{field}.comparison", f"Field {field} {message} {compare_value}")
                )
        except TypeError:
            _logger.debug(
                f"Comparison type error: instance={instance!r}, field={field}, value={value}, comparator={comparator}, compare_value={compare_value}"
            )
            errors.append(
                (
                    f"{field}.comparison",
                    f"Field {field} cannot be compared with {compare_value}",
                )
            )

    return errors
