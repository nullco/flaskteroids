"""Validation errors shared by model records and dependent rich-text records."""

from collections.abc import Iterable, Sequence


class Error:
    def __init__(self, args: Sequence[str]) -> None:
        self._args = args

    @property
    def attribute(self) -> str:
        return self._args[0]

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

    def __iter__(self):
        return iter(self._errors)

    def __getitem__(self, attribute: str) -> list[str]:
        return [
            error.full_message()
            for error in self._errors
            if error.attribute == attribute
            or error.attribute.startswith(f"{attribute}.")
        ]

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
