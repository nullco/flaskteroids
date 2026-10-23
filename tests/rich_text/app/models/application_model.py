from flaskteroids.model import Model


class ApplicationModel(Model):
    __abstract__ = True
    __schema_module__ = "tests.rich_text.db.schema"
