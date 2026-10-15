"""SQLAlchemy type factories for migration/scaffold field arguments.

Input casting belongs to the model's attribute layer, not to generator types.
"""

from functools import partial

import sqlalchemy as sa

_string = partial(sa.String, 255)

fields = {
    "text": sa.Text,
    "string": _string,
    "str": _string,
    "integer": sa.Integer,
    "int": sa.Integer,
    "float": sa.Float,
    "boolean": sa.Boolean,
    "bool": sa.Boolean,
    "datetime": sa.DateTime,
    "date": sa.Date,
    "time": sa.Time,
    "json": sa.JSON,
}
