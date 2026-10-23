import pytest
from sqlalchemy import Column, Integer, Table, Text
from sqlalchemy.orm import declarative_base

from flaskteroids.exceptions import ProgrammerError
from flaskteroids.model import encrypts
from tests.model.schema_support import model_base


@pytest.mark.parametrize("first", ["encrypted", "plain"])
def test_encrypted_tables_require_a_single_model_class(first):
    base = declarative_base()
    Table(
        "shared_records",
        base.metadata,
        Column("id", Integer, primary_key=True),
        Column("secret", Text),
    )
    application_model = model_base(base)

    class EncryptedRecord(application_model):
        __table_name__ = "shared_records"

        encrypts("secret")

    class PlainRecord(application_model):
        __table_name__ = "shared_records"

    model = EncryptedRecord if first == "encrypted" else PlainRecord
    with pytest.raises(ProgrammerError, match="single model"):
        model.prepare()
