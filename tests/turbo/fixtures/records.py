from flaskteroids.model import Model


class ApplicationModel(Model):
    __abstract__ = True
    __schema_module__ = "tests.turbo.fixtures.schema"


class Membership(ApplicationModel):
    pass


class Post:
    def __init__(self, id=None, title="A post"):
        self.id = id
        self.title = title

    def to_key(self):
        return [self.id] if self.id is not None else None

    def to_param(self):
        return "a-url-slug"

    def to_partial_path(self):
        return "posts/post"
