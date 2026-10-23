"""Model declarations and database types for transparent string encryption."""

from flask import current_app
from sqlalchemy import (
    Column,
    Enum,
    String,
    Text,
    UniqueConstraint,
    inspect,
    select,
    type_coerce,
    update,
)
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.sql import operators
from sqlalchemy.types import TypeDecorator

from flaskteroids import encryption
from flaskteroids._models.attributes import cast_input
from flaskteroids.db import session, transactional
from flaskteroids.declarations import EncryptedAttributeDefinition, model_for
from flaskteroids.exceptions import EncryptionError, ProgrammerError
from flaskteroids.rules import bind_rules, declaration


@declaration
def encrypts(*names, deterministic=False, downcase=False):
    """Encrypt string/text attributes; deterministic fields support equality queries."""
    if not names or any(
        not isinstance(name, str) or not name.isidentifier() or name.startswith("_")
        for name in names
    ):
        raise ProgrammerError("encrypts() requires public attribute names")
    if type(deterministic) is not bool or type(downcase) is not bool:
        raise ProgrammerError("Encryption options must be booleans")
    definition = EncryptedAttributeDefinition(deterministic, downcase)

    def bind(cls):
        for name in names:
            model_for(cls).encrypted_attributes[name] = definition

    return bind


class EncryptedAttribute(TypeDecorator):
    impl = Text
    cache_ok = True
    should_evaluate_none = True

    def __init__(self, plaintext_type, context, definition):
        super().__init__()
        self.plaintext_type = plaintext_type
        self.context = context
        self.definition = definition
        self.impl = plaintext_type

    def normalize(self, value):
        value = cast_input(self.plaintext_type, value)
        return (
            value.lower() if value is not None and self.definition.downcase else value
        )

    def process_bind_param(self, value, dialect):
        result = encryption.encrypt(
            self.normalize(value),
            context=self.context,
            deterministic=self.definition.deterministic,
        )
        if result is not None and self.impl.length and len(result) > self.impl.length:
            raise EncryptionError(
                f"Ciphertext exceeds the column size for {self.context}; "
                "use a text column or increase its size"
            )
        return result

    def process_result_value(self, value, dialect):
        return encryption.decrypt(
            value, context=self.context, deterministic=self.definition.deterministic
        )

    class Comparator(TypeDecorator.Comparator):
        def operate(self, op, *other, **kwargs):
            null_test = (
                op in {operators.eq, operators.ne, operators.is_, operators.is_not}
                and len(other) == 1
                and other[0] is None
            )
            equality = op in {
                operators.eq,
                operators.ne,
                operators.in_op,
                operators.not_in_op,
            }
            column_identity = (
                op in {operators.eq, operators.ne}
                and len(other) == 1
                and isinstance(other[0], Column)
                and self.expr.table is other[0].table
                and self.expr.key == other[0].key
            )
            if not (null_test or column_identity) and not (
                self.type.definition.deterministic and equality
            ):
                raise EncryptionError(
                    "Encrypted attributes support only deterministic equality "
                    "queries and NULL checks"
                )
            return super().operate(op, *other, **kwargs)

        def reverse_operate(self, op, other, **kwargs):
            raise EncryptionError("Unsupported operation on an encrypted attribute")

    comparator_factory = Comparator


def column_types(model, table):
    result = {}
    for name, definition in model_for(model).encrypted_attributes.items():
        column = table.columns.get(name)
        if column is None:
            raise ProgrammerError(
                f"Encrypted attribute {model.__name__}.{name} needs a column"
            )
        if not isinstance(column.type, String) or isinstance(column.type, Enum):
            raise ProgrammerError("Encrypted attributes require string or text columns")
        if column.primary_key or column.foreign_keys:
            raise ProgrammerError("Primary and foreign keys cannot be encrypted")
        if column.server_default is not None:
            raise ProgrammerError(
                "Encrypted columns cannot have plaintext server defaults"
            )
        if not definition.deterministic and (
            column.unique
            or any(index.unique and name in index.columns for index in table.indexes)
            or any(
                isinstance(constraint, UniqueConstraint) and name in constraint.columns
                for constraint in table.constraints
            )
        ):
            raise ProgrammerError("Encrypted unique indexes require deterministic=True")
        result[name] = EncryptedAttribute(
            column.type, f"{model.__name__}.{name}", definition
        )
    return result


class EncryptableRecord:
    @classmethod
    def encrypted_attributes(cls):
        bind_rules(cls)
        return frozenset(model_for(cls).encrypted_attributes)

    def ciphertext_for(self, name):
        current_app.extensions["flaskteroids.db"].require_model(type(self))
        if inspect(self).was_deleted:
            raise ProgrammerError("A destroyed record has no stored ciphertext")
        if name not in self.encrypted_attributes():
            raise AttributeError(f"{name!r} is not an encrypted attribute")
        column = self.__table__.c[name]
        if self.is_new_record() or name in self.changes:
            return column.type.process_bind_param(getattr(self, name), None)

        return session.scalar(
            select(type_coerce(column, Text())).where(
                *(
                    key == value
                    for key, value in zip(
                        inspect(type(self)).primary_key,
                        inspect(self).identity,
                        strict=True,
                    )
                )
            )
        )

    @transactional
    def encrypt(self):
        """Re-encrypt declared attributes without saving unrelated staged changes."""

        current_app.extensions["flaskteroids.db"].require_model(type(self))
        if not self.is_persisted():
            raise ProgrammerError("Save a record before re-encrypting its attributes")
        values = {
            name: self.__table__.c[name].type.normalize(getattr(self, name))
            for name in self.encrypted_attributes()
        }
        if values:
            session.execute(
                update(self.__table__)
                .where(
                    *(
                        key == value
                        for key, value in zip(
                            inspect(type(self)).primary_key,
                            inspect(self).identity,
                            strict=True,
                        )
                    )
                )
                .values(**values)
            )
            for name, value in values.items():
                set_committed_value(self, name, value)
                self._changes.pop(name, None)
                self._raw_attributes.pop(name, None)
        return True
