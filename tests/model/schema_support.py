"""Explicit snapshot fixtures, built from static test table declarations."""

import sys
from types import ModuleType
from uuid import uuid4

from sqlalchemy import MetaData
from sqlalchemy.orm import relationship

from flaskteroids.model import Model


def model_base(base, relationships=None):
    module_name = f"test_model_schema_{uuid4().hex}"
    module = ModuleType(module_name)
    module.metadata = MetaData()
    for table in base.metadata.tables.values():
        table.to_metadata(module.metadata)
    sys.modules[module_name] = module

    def prepare(cls, **kwargs):
        for name, options in (relationships or {}).get(cls.__name__, {}).items():
            setattr(cls, name, relationship(**options))

    return type(
        "ApplicationModel",
        (Model,),
        {
            "__abstract__": True,
            "__schema_module__": module_name,
            "__init_subclass__": classmethod(prepare),
        },
    )
