from sqlalchemy.exc import DontWrapMixin


class ProgrammerError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class DoubleRenderError(ProgrammerError):
    pass


class StrictLoadingViolationError(ProgrammerError):
    pass


class EncryptionError(ProgrammerError, DontWrapMixin):
    pass


class UserError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class RecordInvalid(Exception):
    """An association write rejected a target or join record."""

    def __init__(self, record):
        self.record = record
        super().__init__(f"{type(record).__name__} could not be saved")


class RecordNotFoundException(Exception):
    pass


class SerializationError(ProgrammerError):
    pass


class DeserializationError(Exception):
    pass


class InvalidParameter(UserError):
    pass


class MissingParameter(UserError):
    pass
