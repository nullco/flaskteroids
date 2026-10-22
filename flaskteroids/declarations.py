"""Class-owned declarations. These records never contain application resources."""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, TypedDict

if TYPE_CHECKING:
    from flaskteroids.attachments.attached import Definition
    from flaskteroids.callbacks import Callback
    from flaskteroids.model import Model


@dataclass
class RuleDefinition:
    entries: list[Callable] = field(default_factory=list)
    bound: bool = False


@dataclass
class ActionDefinition:
    names: list[str] = field(default_factory=list)
    before: dict[str, list[str]] = field(default_factory=dict)
    around: dict[str, list[str]] = field(default_factory=dict)
    after: dict[str, list[str]] = field(default_factory=dict)
    originals: dict[str, Callable] = field(default_factory=dict)
    helpers: dict[str, str] = field(default_factory=dict)
    prepared: bool = False


@dataclass(frozen=True)
class AssociationDefinition:
    name: str
    kind: Literal["belongs_to", "has_many", "has_one"]
    target: str
    foreign_key: str
    dependent: str | None = None
    inverse_of: str | None = None
    optional: bool = False


class VirtualFieldConfig(TypedDict, total=False):
    read_only: bool
    cache: bool
    set_fn: Callable[["Model"], None]


@dataclass
class ModelDefinition:
    validators: list[Callable[..., Iterable[Sequence[str]]]] = field(
        default_factory=list
    )
    virtual_fields: dict[str, VirtualFieldConfig] = field(default_factory=dict)
    password_field: str | None = None
    callbacks: dict[str, list["Callback"]] = field(default_factory=dict)
    associations: dict[str, AssociationDefinition] = field(default_factory=dict)
    attachments: dict[str, "Definition"] = field(default_factory=dict)


def model_for(cls: type) -> ModelDefinition:
    name = "_flaskteroids_model"
    if name not in vars(cls):
        setattr(cls, name, ModelDefinition())
    return vars(cls)[name]


def rules_for(cls: type) -> RuleDefinition:
    name = "_flaskteroids_rules"
    if name not in vars(cls):
        setattr(cls, name, RuleDefinition())
    return vars(cls)[name]


def actions_for(cls: type) -> ActionDefinition:
    name = "_flaskteroids_actions"
    if name not in vars(cls):
        setattr(cls, name, ActionDefinition())
    return vars(cls)[name]
