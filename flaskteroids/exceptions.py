class ProgrammerError(Exception):

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class UserError(Exception):

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class InvalidParameter(UserError):
    pass


class MissingParameter(UserError):
    pass
