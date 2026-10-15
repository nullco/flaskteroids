# ORM replacement: generated snapshots and lazy native mappings

Status: full replacement authorized on the experimental branch. This document
records the project owner's final decisions and supersedes the earlier
exploration, hand-written-schema, and eager schema-inheritance proposals.
Backward compatibility and a supported dual-ORM mode are not requirements.

## Confirmed architecture

1. **Migrations are authoritative.** Generate `app/schema.py` from the database
   after successful migration/preparation/rollback. Commit the generated snapshot;
   do not maintain column declarations independently or edit the snapshot by hand.
2. **Keep ordinary application boot.** `flask db:migrate`, `db:prepare`, and
   `db:schema:dump` use normal Flask application initialization. There is no
   migration-only application, skipped initializer mode, or alternate bootstrap.
   An initializer that actually uses an unavailable model still fails normally.
3. **Declare now, map when needed.** Importing a model collects its behavior and
   rules without requiring a snapshot or a table. Construction, facade queries,
   and mapped attribute expressions prepare the required relationship graph.
   Native callers can explicitly use `Model.prepare()` before APIs such as
   `sqlalchemy.inspect(Model)` or `session.get(Model, id)`.
4. **Keep decorator signatures.** Associations remain declarations inside
   `@rules(belongs_to(...), has_many(...), ...)`, not a replacement class-attribute
   DSL. Translate these declarations into native SQLAlchemy relationships before
   publishing mappers. Native `relationship()` is also available when needed.
5. **Use actual mapped application objects.** No `_base_instance`, hidden mapped
   row class, wrapper conversion, second identity map, or relationship cache.
   SQLAlchemy owns published attribute history, identity, relationship loading,
   and the unit of work.
6. **Retain bounded scalar staging.** The owner explicitly approved `_changes` on
   the mapped application object. Assignment retains typed pending values and
   original input. A successful save publishes them to that same object's
   instrumented attributes. Failed scalar validation leaves published state
   untouched, so later queries, other saves, and teardown cannot leak those edits.
7. **Keep teardown auto-commit.** Commit if no exception reaches app-context
   teardown, otherwise roll back, and always close the session. A handled
   validation failure or HTTP error response does not itself force rollback.
   `save()` validates and flushes; it does not commit the surrounding transaction.

There is no longer a requirement for `schema.Post` to exist, or for application
classes to inherit schema mixins. Bind `Post` to the snapshot's `posts` Table via
SQLAlchemy's public imperative mapping API, lazily and on the actual class.
This preserves the desired field-free model experience without mutable bases.

## Developer experience

```python
# app/models/application_model.py
from flaskteroids.model import Model

class ApplicationModel(Model):
    __abstract__ = True
```

```python
# app/models/author.py
from app.models.application_model import ApplicationModel
from flaskteroids.model import has_many, validates
from flaskteroids.rules import rules

@rules(has_many("posts", dependent="destroy"), validates("name", presence=True))
class Author(ApplicationModel):
    pass
```

```python
# app/models/post.py
from app.models.application_model import ApplicationModel
from flaskteroids.model import belongs_to, validates
from flaskteroids.rules import rules

@rules(belongs_to("author"), validates("title", presence=True))
class Post(ApplicationModel):
    pass
```

```sh
flask generate model Author name:string
flask generate model Post title:string author:references
flask db:prepare
# app/schema.py is now generated from the migrated database.
```

```python
author = Author.create(name="Ada")
post = Post.create(title="First", author=author)
authors = Author.where(Author.name.ilike("a%")).includes("posts").all()

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from flaskteroids.db import session

# Native and facade queries share mapped instances and published database state.
native = session.scalars(select(Author).options(selectinload(Author.posts))).all()
assert native[0] is authors[0]
```

## Snapshot ownership and workflow

The snapshot contains SQLAlchemy metadata for all reflectable tables in the
selected database, including tables without application models and framework
attachment tables. Exclude Alembic's bookkeeping table. Foreign-key targets can
therefore resolve without requiring a behavioral model for every table.

- Reflection belongs only to schema-dump tooling, never model import/mapping.
- Use public SQLAlchemy reflection and Alembic rendering APIs. Snapshot import
  constructs metadata only; it must never connect or execute migrations.
- Publish the snapshot atomically after successful rendering/compilation. A dump
  failure preserves the previous file. Preserve ordinary read permissions.
- A migration may already be applied when snapshot publication fails. Report
  that distinction; fix the cause and rerun `db:schema:dump`. Do not pretend that
  a failed file write rolled the database back.
- Restart running application/worker processes after schema changes. Do not
  reload snapshots or mutate already-published mappings in place.
- Standalone migration generation does not edit snapshots. Renames, data
  migrations, triggers, and unsupported changes remain explicit migration work.
- Runtime model metadata is not desired-schema input for Alembic autogeneration.
  Alembic remains the migration runner and supplies public snapshot rendering.
- A snapshot is not a data backup or universal database export. Unsupported
  reflected types fail explicitly. Review dialect-specific output and backend
  differences before committing a snapshot generated from another environment.

## Mapping and application isolation

An abstract base under `<application>.models` infers `<application>.schema`.
An explicit `__schema_module__` is available for custom/test model sets.
`__table_name__` overrides the default tableized class name when necessary.

Each application model base owns its catalog, registry, metadata, and mapping
lock. Model discovery imports modules deterministically but does not map them.
At first use, clone snapshot tables into the owned metadata, bind rules, validate
all required relationship targets/columns, then map/configure the required graph.
Missing snapshots/tables are first-use errors with migration guidance, not import
errors. Preflight failures must not publish a partial graph.

- Abstract behavior bases share their root registry and do not require tables.
- Reject duplicate class names within a model set, combining different roots,
  concrete model inheritance, inline column declarations, and schema/API name
  collisions. Ordinary repeated imports preserve class identity.
- Decorators run before mapping. Association installation is not incremental
  mutation of already-published mappers.
- SQLAlchemy handles cyclic string targets, inverse synchronization, loader
  strategies, foreign keys, and native unit-of-work failures.
- Different model sets have different registries. Do not use global mapper
  resets or process-global bare-name model caches.
- One mapped class set may serve multiple engines/sessions with matching schemas.
  Incompatible schemas fail at actual database use; a snapshot is not runtime
  schema validation or a per-engine reflection cache.

Dynamic fields remain a deliberate editor/static-inference limitation. Keep the
repository's scoped mypy checks intact; generated stubs are optional follow-up
work, not a reason to reintroduce row wrappers or explicit column inheritance.

## Staging, validation, defaults, and native boundaries

Ordinary scalar reads expose staged values. SQLAlchemy inspection/history and
SQL expressions see published state. This is intentional, not fully transparent
native attribute-state interoperability.

- `save()` returns a success boolean. Invalid `create()` returns the unsaved
  object with values/errors; invalid `update()` preserves entered values.
- Queries do not publish edits. A valid-but-unsaved edit is not implicitly saved
  at commit, including edits made after an earlier successful save.
- Use `apply_changes()` to publish staged scalars explicitly without framework
  validation/callbacks before native `add()`/`flush()`. Reject unpublished staged
  new objects enrolled directly into a native unit of work rather than silently
  inserting null/default values.
- Native collection/relationship mutations and configured mutable-value types
  have native unit-of-work semantics; they are not scalar staging. Correct or
  remove invalid transient children in collections when abandoning their save.
- Saving a graph validates newly associated framework objects before publishing
  them. SQLAlchemy may flush other already-published native work. Constraints
  remain authoritative, including races validation cannot prevent.
- Database and unexpected callback exceptions propagate. If caught inside an
  application context, recover/roll back explicitly before further writes.
- `reload()` discards staged input and errors. Native refresh/expiration changes
  published state but does not itself discard the pending input dictionary.
- Cast at the model layer and retain before-type-cast values for validation and
  form redisplay. Numericality checks raw input, not a permissive numeric cast.
- JSON/form output must exclude authentication secrets and reset tokens by
  default. Never log raw input as part of framework representations.

### Defaults

Python `Column.default` functions cannot be reconstructed from a database and
are no longer a separate constructor-default mechanism. Put persistent defaults
in migrations. Decode simple SQL literal server defaults for new model values;
leave SQL functions, computed values, identities, and complex expressions to the
server. No evaluation SQL is issued during construction.

Explicit null input must not accidentally request a server default. Non-primary
key mapped types evaluate explicit `None`; JSON retains its native JSON-null
semantics. Absent server-generated values remain absent until flush. Mutable
literal defaults are decoded independently for each new instance. Application
Python defaults belong in explicit behavior/callbacks, not the generated file.

The Rails 8.0.2 references used for casting/failure behavior are:

- [Validation/save](https://github.com/rails/rails/blob/v8.0.2/activerecord/lib/active_record/validations.rb)
- [Persistence](https://github.com/rails/rails/blob/v8.0.2/activerecord/lib/active_record/persistence.rb)
- [Before type cast](https://github.com/rails/rails/blob/v8.0.2/activerecord/lib/active_record/attribute_methods/before_type_cast.rb)
- [Integer casting](https://github.com/rails/rails/blob/v8.0.2/activemodel/lib/active_model/type/integer.rb)
- [Boolean casting](https://github.com/rails/rails/blob/v8.0.2/activemodel/lib/active_model/type/boolean.rb)
- [Numericality](https://github.com/rails/rails/blob/v8.0.2/activemodel/lib/active_model/validations/numericality.rb)

## Compatibility/contract matrix

| Concern | Replacement contract / deliberate change |
| --- | --- |
| Model declarations | Field-free application models; generated table snapshot, not reflected row wrappers or schema inheritance. |
| Queries | Immutable/lazy facade, SQLAlchemy expressions/options, mapped results; `all()` returns a list. |
| Ordering/pagination/count | Deterministic default primary-key order; count respects the selected scope/page; `last()` materializes that scope. |
| Eager loading | Native loaders; dotted `includes("posts.author")` paths; unknown paths fail clearly. |
| Associations | Keep `@rules` helper signatures; native collections replace custom `Relation`; create via `Post.create(author=author)`. |
| Dependent destruction | `dependent="destroy"` invokes child framework `destroy()`; native ORM/DB cascades do not imply child framework callbacks. |
| Callbacks | Explicit framework operations; load callbacks run on actual hydration, not every identity-map lookup; native/bulk operations bypass framework lifecycle guarantees. |
| Commit hooks | Deferred to the outer transaction; no after-commit dispatch for rolled-back operations. |
| Authentication | Password/reset checks use published digests; failed staged password edits do not invalidate persisted credentials. |
| Attachments | Existing deferred upload/commit/rollback integration on mapped objects; retain pending attachment input separately from scalar changes. |
| Jobs | Keep existing queue contracts; pass persisted identities rather than assuming arbitrary mapped instances are JSON job arguments. |
| Missing tables | No startup reflection; missing snapshot tables fail when needed; live database drift remains a native database error. |
| Test helpers | Load selected fixture models only; do not map unrelated unmigrated declarations merely to match table names. |

## Obsolete machinery removed or replaced

- Hidden mapped-row wrappers and result conversion in `_models/records.py`.
- Reflected model bindings, row-table projections, association caches, and custom
  `Relation` loading/persistence. Retain only decorator-to-relationship helpers.
- Generator-driven `schema_source()` and manually maintained schema mixins.
- Eager startup mapping and declarative-only `__allow_unmapped__` configuration.
- Duplicate `Field.as_primitive()` / `from_column_type()` casting. Generator field
  names now map to SQLAlchemy type factories; model casting has one owner.
- Hand-written-schema and eager-inheritance tests/documentation. Preserve their
  valuable public guarantees as snapshot/lazy-mapping tests instead.

## Verification

Run focused model, snapshot, isolation, and generated-application tests during
implementation, then the full suite and repository quality checks:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Keep the Python 3.12–3.15 browser-enabled CI matrix and scoped typing targets.
Generated application checks must exercise ordinary startup before first migration,
a create migration and later field change, automatic snapshots and rollback,
forms/errors/raw input, native/facade identity, eager-loading query counts,
authentication, attachments, callbacks/transactions, and test isolation. Run the
integration suite against each supported external backend when available; a
local SQLite run alone is not PostgreSQL/MySQL verification.
