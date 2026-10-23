import os

import pytest
from app.models.deferred_record import DeferredRecord
from sqlalchemy.engine import make_url
from wsgi import app

from flaskteroids.exceptions import ProgrammerError

assert app.env.test
assert make_url(app.database_url) == make_url(os.environ["FLASKTEROIDS_DATABASE_URL"])
with app.app_context():
    assert app.make_shell_context()["DeferredRecord"] is DeferredRecord
    assert "__mapper__" not in vars(DeferredRecord)
    with pytest.raises(ProgrammerError, match="DeferredRecord.*migrations"):
        DeferredRecord.first()
assert app.test_client().get("/up/").status_code == 200
