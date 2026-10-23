"""Scalar staging on the mapped object; no hidden row or alternate identity map."""

from sqlalchemy import inspect
from sqlalchemy.orm import MANYTOONE

from flaskteroids._models.associations import AssociationCollection
from flaskteroids._models.attributes import cast_input, database_value
from flaskteroids._models.encryption import EncryptedAttribute
from flaskteroids.declarations import model_for
from flaskteroids.rich_text.attribute import association_value


class StagedAttributes:
    def __getattribute__(self, name):
        if not name.startswith("_"):
            pending = object.__getattribute__(self, "__dict__").get("_changes", {})
            if name in pending:
                return pending[name]
            if (
                name.startswith("rich_text_")
                and name[10:] in model_for(type(self)).rich_texts
            ):
                return association_value(self, name[10:])
            association = model_for(type(self)).associations.get(name)
            if association is not None and association.kind == "has_many":
                return AssociationCollection(self, name)
        return super().__getattribute__(name)

    def __setattr__(self, name, value):
        if not name.startswith("_"):
            mapper = inspect(type(self), raiseerr=False)
            if mapper is not None and name in mapper.column_attrs:
                column = mapper.column_attrs[name].columns[0]
                pending = self.__dict__.setdefault("_changes", {})
                raw = self.__dict__.setdefault("_raw_attributes", {})
                pending[name] = (
                    column.type.normalize(value)
                    if isinstance(column.type, EncryptedAttribute)
                    else cast_input(column.type, value)
                )
                raw[name] = value
                return
            if mapper is not None and name in mapper.relationships:
                # Explicit relationship assignment takes precedence over an
                # earlier, staged foreign-key assignment for that relationship.
                relationship = mapper.relationships[name]
                if not relationship.uselist:
                    if value is not None and not isinstance(
                        value, relationship.mapper.class_
                    ):
                        raise TypeError(
                            f"{type(self).__name__}.{name} expects "
                            f"{relationship.mapper.class_.__name__} or None"
                        )
                    for column in (
                        relationship.local_columns
                        if relationship.direction is MANYTOONE
                        else ()
                    ):
                        key = mapper.get_property_by_column(column).key
                        self.__dict__.get("_changes", {}).pop(key, None)
                        self.__dict__.get("_raw_attributes", {}).pop(key, None)
        super().__setattr__(name, value)

    @property
    def changes(self):
        """Pending typed scalar values, not SQLAlchemy's published history."""
        return dict(self.__dict__.get("_changes", {}))

    @property
    def saved_changes(self):
        """Typed changes from the latest successful framework save."""
        return dict(self._saved_changes)

    def saved_change_to_attribute(self, name):
        return self._saved_changes.get(name)

    def attribute_before_last_save(self, name):
        change = self.saved_change_to_attribute(name)
        return change[0] if change is not None else self.read_published_attribute(name)

    def read_published_attribute(self, name):
        """Read SQLAlchemy-managed scalar state without staged input overrides."""
        if name not in inspect(type(self)).column_attrs:
            raise AttributeError(f"Unknown attribute {type(self).__name__}.{name}")
        return super().__getattribute__(name)

    def read_attribute_before_type_cast(self, name):
        mapper = inspect(type(self))
        if name not in mapper.column_attrs:
            raise AttributeError(f"Unknown attribute {type(self).__name__}.{name}")
        raw = self.__dict__.get("_raw_attributes", {})
        return raw[name] if name in raw else getattr(self, name)

    @property
    def attributes_before_type_cast(self):
        return {
            name: self.read_attribute_before_type_cast(name)
            for name in inspect(type(self)).column_attrs.keys()
        }

    def apply_changes(self):
        """Publish staged scalars without validation/callbacks for native ORM use."""
        mapper = inspect(type(self))
        pending = self.__dict__.get("_changes", {})
        raw = self.__dict__.get("_raw_attributes", {})
        for name, value in pending.items():
            column = mapper.column_attrs[name].columns[0]
            # Bypass staging, but still invoke SQLAlchemy's InstrumentedAttribute.
            super().__setattr__(name, database_value(column.type, value, raw[name]))
        pending.clear()
        raw.clear()
        return self

    def discard_changes(self):
        """Discard only staged scalar input, leaving published ORM state intact."""
        self.__dict__.get("_changes", {}).clear()
        self.__dict__.get("_raw_attributes", {}).clear()
        return self
