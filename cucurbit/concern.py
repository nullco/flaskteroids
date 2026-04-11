class Concern:

    def __getattribute__(self, name: str, /):
        return super().__getattribute__(name)
