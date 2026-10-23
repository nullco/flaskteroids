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
