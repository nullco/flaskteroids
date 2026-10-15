# Model loading notes

The initial experiment found that adding relationships to a live SQLAlchemy
mapping could leave it broken after an error. Unresolved foreign keys also made
independent writes difficult.

The chosen approach leaves working mappings alone: model declarations come first,
and association queries run when needed. The reflected schema is retained
separately from the row mapping.

Regression coverage lives in `test_lazy_models.py`, `test_models.py`, and
`../model/`. The [application integration tests](../integration/README.md) exercise
the same workflows with SQLite, PostgreSQL, and MySQL.
