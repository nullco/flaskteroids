# Explore Rails-like models with automatic schema inheritance

Status: proposed exploration, not an approved migration.

## Purpose

Evaluate a hybrid model layer: SQLAlchemy declarations in `app/schema.py`,
automatically composed into same-named Flaskteroids models, with Rails-like
querying, validation, and persistence APIs.

The primary experiment is convention-based schema inheritance. Application model
classes should only need to inherit `ApplicationModel`: Flaskteroids finds the
same-named declaration in `app.schema` and incorporates it during class creation.
Fields stay out of behavioral model classes without requiring explicit schema
imports or inheritance in each model.

The goal is not to replace the Rails-like application API with session calls.
Preserve the convenient experience of `Author.where(...)`, `Author.find(...)`,
`Author.create(...)`, and `author.save()` while removing database-first reflection
and the separate framework-wrapper/mapped-row architecture.

The hypothesis is that SQLAlchemy can own mapping, identity, attribute state,
relationships, and the unit of work, while Flaskteroids supplies an ergonomic API,
validation, callbacks, conventions, and integrated tooling. Native SQLAlchemy APIs
should remain usable on the same objects and in the same session.

Do not rewrite the existing ORM as part of this exploration. Build a small,
isolated prototype, compare it with the current implementation, and record a
proceed, revise, or stop decision. This document does not supersede the existing
`plan-1.md`, `plan-2.md`, or `plan-3.md` work.

## Why investigate

The current model layer owns more than convenience methods:

- `flaskteroids/model.py` wraps a separate mapped `_base_instance` and maintains
  pending changes, attribute dispatch, and persistence operations.
- `flaskteroids/_models/records.py` constructs framework wrappers around mapped
  query results.
- `flaskteroids/_models/query.py` provides a query interface and result conversion.
- `flaskteroids/_models/associations.py` provides framework-managed associations.
- `flaskteroids/extensions/db.py` reflects tables, constructs persistence mappings,
  and resolves model bindings and association declarations.

This creates overlapping object/state systems and makes Flaskteroids responsible
for reconciling them. Reflection, lazy mapping, relationship configuration,
identity, dirty tracking, and failure isolation all contribute to that cost.

`tests/isolation/incremental_mapping_spike.md` documents concrete difficulties
with incremental relationship installation and unresolved reflected foreign keys.
Those probes motivate this exploration; they are not proof that reflection is
universally wrong or that native mappings solve every isolation requirement.

## Separate the decisions

Evaluate these independently rather than treating them as one package:

1. **Schema mapping:** database-first reflection versus explicit mapped columns.
2. **Declaration placement/composition:** inline fields versus a separate schema
   module with explicit or automatic same-name inheritance.
3. **Object model:** framework wrapper versus the actual SQLAlchemy-mapped object.
4. **Query API:** custom chaining versus SQLAlchemy expressions and statements.
5. **Persistence API:** Active Record-style `save()` versus session/unit-of-work
   operations.
6. **Framework integration:** conventions, validation, forms, authentication,
   attachments, generators, migrations, and testing.

The primary candidate combines explicit SQLAlchemy declarations in `app.schema`,
automatic same-name composition, actual mapped application objects, and Rails-like
query/persistence methods. Explicit schema inheritance and native-only application
code are comparison baselines, not the intended default developer experience.

SQLAlchemy field declarations (`Mapped`, `mapped_column`, `ForeignKey`, and native
types) replace reflected column discovery. Start with native `relationship()`
declarations too; whether association declaration helpers remain is a separate
question. Rails-like methods are first-class APIs to investigate, not merely
legacy compatibility shims. Their implementation must delegate to SQLAlchemy
rather than maintain a second object/state system.

## Candidate experience

Illustrative only; the base-class import and declaration conventions are not yet
public API decisions:

```python
# app/schema.py — unmapped declarations, not a second set of mapped models
from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship


class Author:
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

    @declared_attr
    def posts(cls) -> Mapped[list["Post"]]:
        return relationship("Post", back_populates="author")


class Post:
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"))

    @declared_attr
    def author(cls) -> Mapped["Author"]:
        return relationship("Author", back_populates="posts")
```

```python
# app/models/author.py
from app.models.application_model import ApplicationModel


class Author(ApplicationModel):
    def greeting(self):
        return f"Hello, {self.name}"
```

```python
# app/models/post.py
from app.models.application_model import ApplicationModel


class Post(ApplicationModel):
    pass
```

Conceptually, class creation produces `Author(schema.Author, ApplicationModel)`
and `Post(schema.Post, ApplicationModel)` before declarative mapping takes place.
Application model files do not need to write those bases themselves. Relationship
strings must resolve to the resulting mapped application classes, not schema
mixins; the prototype must prove this.

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.author import Author
from app.models.post import Post
from flaskteroids.db import session


# Rails-like API for routine application code.
author = Author(name="Ada")
if author.save():
    post = Post.create(title="First post", author=author)
else:
    errors = author.errors

authors = Author.where(name="Ada").includes("posts").all()
matching = Author.where(Author.name.ilike("a%"))
found = Author.find(author.id)  # Raises the framework's not-found exception.

# Native SQLAlchemy remains available on those same mapped classes/instances.
statement = (
    select(Author)
    .where(Author.name == "Ada")
    .options(selectinload(Author.posts))
)
native_authors = session.scalars(statement).all()
```

The application object should be the mapped object: no hidden row instance,
wrapper conversion, duplicate identity map, or parallel pending-change store.

`ApplicationModel` would be an abstract SQLAlchemy declarative base with
Flaskteroids API methods. A compatible class-creation mechanism looks up the schema
declaration and includes it before SQLAlchemy maps each concrete model. The exact
mechanism is an experimental outcome, not a mandate to use a particular metaclass.
Do not modify bases or install schema fields after a mapper has been published.

Schema classes remain unmapped declaration mixins. Only application models are
mapped: inheriting an already-mapped schema class would invoke SQLAlchemy mapped
inheritance rather than simply supplying fields. Framework methods operate on
`self` and the app's session; query results are those same mapped instances.

A shared base may eventually supply table names, IDs, or timestamps. Start with
explicit schema declarations so the mapping behavior is visible. Keep framework
validation/callback declarations and business behavior in application model files.
SQLAlchemy field types do not replace form coercion or user-facing validation.

The example is a target shape, not a promise that the current API can be copied
unchanged. In particular, define `save()`/`create()` validation, flush, failure, and
transaction semantics before implementing them.

### Accepted convention and tooling trade-off

Prefer the Rails-like model experience for this experiment. Dynamic schema
inheritance may prevent ordinary static analyzers and editors from seeing model
fields, even though the declarations in `schema.py` are typed. This is an accepted
trade-off to evaluate, not by itself a stop condition or a requirement to switch
back to explicit inheritance.

Rails makes a comparable trade-off for schema-backed attributes; richer tooling
often relies on schema awareness or generated definitions. Record actual Python
completion/type-checking behavior. Generated stubs or schema-aware tooling are
possible follow-ups, not prerequisites for proving the architecture. Keep the
repository's existing scoped typing checks intact; do not expand their scope to
require static inference of these experimental fields.

The intended magic is bounded class-creation-time composition, not per-access
proxying, duplicate state, or synchronization between two model objects.

### Ownership boundary

| Concern | Owner in the hybrid candidate |
| --- | --- |
| Columns, types, foreign keys, metadata | Unmapped SQLAlchemy declarations in `app.schema` |
| Same-name schema lookup and pre-mapping composition | Flaskteroids class-creation convention |
| Mapped instances, identity, dirty tracking, unit of work | SQLAlchemy |
| Relationship loading and persistence | SQLAlchemy relationships |
| `where`, `find`, `includes`, ordering, pagination | Flaskteroids facade over SQLAlchemy statements/loaders |
| `save`, `create`, `update`, `destroy` | Flaskteroids operations on mapped instances/session |
| Validation, errors, form integration | Flaskteroids, with explicit interaction with flush |
| Callbacks and post-commit work | Flaskteroids contracts integrated with SQLAlchemy lifecycle |
| Generators, migration workflow, common conventions | Flaskteroids |

No custom metaclass attribute forwarding, row-wrapper conversion, parallel dirty
tracking, or independent relationship cache should be required. SQLAlchemy's
public inspection/history APIs should supply persistence state where needed.

## Phase 1: inventory the contracts

Before prototyping, distinguish valuable application behavior from implementation
details. Review public APIs and existing tests, including generated applications.

Produce a short matrix: current behavior, proposed hybrid behavior, compatibility
impact, and whether the behavior is essential or negotiable. Treat Rails-like
querying, validation/errors, and persistence methods as core prototype goals;
record any semantic changes needed to make them cooperate with SQLAlchemy.

Include:

- Querying, not-found handling, ordering, pagination, and eager loading.
- Assignment/coercion, defaults, transient fields, and serialization exclusions.
- Relationship assignment, inverse synchronization, and dependent deletion.
- Validation errors and form redisplay after an unsuccessful submission.
- Persistence callbacks, timestamps, and after-commit side effects.
- Authentication, attachments, and job serialization of model references.
- Transaction ownership, rollback, test isolation, and multiple applications.
- Model/scaffold generators, migrations, schema setup, and CLI discovery.

Do not assume every existing behavior must survive unchanged. Record deliberate
changes rather than silently dropping contracts.

## Phase 2: prove schema composition, then build a vertical slice

Use an experimental branch or isolated example/test application. Keep the current
production path intact; do not add a supported dual-ORM mode merely to run a spike.
Use public SQLAlchemy APIs and the project's locked environment.

### First: class-creation spike

Prove the automatic convention before porting controllers or integrations:

- A bare `class Author(ApplicationModel)` receives fields from `app.schema.Author`
  before declarative mapping. Importing schema and model modules performs no
  database I/O and works before migrations have run.
- Schema mixins have no mappers of their own. SQLAlchemy inspection of the final
  application classes exposes the expected fields and relationships.
- An Author/Post relationship pair resolves to application model classes, supports
  inverse assignment and eager loading, and uses normal SQLAlchemy persistence.
- Framework and native lookups of the same row return the same object within one
  session. No hidden row classes, wrapper conversion, or parallel dirty tracking
  are introduced.
- Ordinary Python methods, properties, and framework declarations remain usable;
  define and test collisions between schema fields and framework/model APIs.
- Abstract `ApplicationModel` and other abstract bases skip schema lookup. Define
  behavior for missing schemas, duplicate/ambiguous names, model inheritance,
  explicit overrides, and repeated imports. Default failures should be clear;
  never silently fall back to database reflection.
- Schema lookup uses the intended application's module, not a process-global
  bare-name cache. Test separate applications with same-named model classes, and
  distinguish this from sharing one model set across multiple engines.

Explicit inheritance can be a diagnostic control. Do not stop at that control:
automatic same-name composition is the hypothesis to test. If it cannot be made
reliable with supported SQLAlchemy behavior, record the blocker before proposing
an alternative.

### Then: application slice

Build an Author/Post slice containing:

1. SQLAlchemy schema declarations and native relationships, with field-free
   application models automatically composed by name.
2. A migration creating the schema and a subsequent migration changing a field.
3. Create/update forms using Rails-like persistence methods, with validation
   failures, `errors`, and preservation of entered values.
4. A listing using `where`/`includes`, plus a native SQLAlchemy equivalent; verify
   eager loading avoids per-row queries in both paths.
5. A transaction combining Rails-like methods and native session operations,
   including a failure that rolls back changes to both models.
6. A deletion example using `destroy()` with explicit ORM/database cascade choices.
7. A small generated-model/scaffold example updating `app/schema.py`, creating a
   behavior-only model file, and generating Rails-like controller code.
8. Identity/state tests showing that facade and native queries share the same
   mapped instances and observe the same pending changes.

Show the complete model, controller, form, migration, and test code. Compare the
current implementation, hybrid candidate, and a small native-only baseline, not
just a shorter model declaration.

### Resolve these design questions explicitly

**Rails-like query facade**

- Can `where` accept both keyword filters and SQLAlchemy expressions without
  attribute forwarding to another class?
- Can `includes` translate to native loader options using mapped relationships?
  Define supported nesting and error behavior rather than rebuilding a loader.
- Define chaining, query reuse/mutability, execution, return types, and not-found
  behavior. Test ordering, pagination, and count semantics.
- Provide a clear way to use native statements/options for complex joins,
  aggregates, and subqueries. Do not attempt to reproduce all of SQLAlchemy's API.
- Do both paths return mapped objects directly? Record typing/completion limits
  without treating dynamic-field inference as a prerequisite.

**Sessions and transactions**

- Who begins, commits, rolls back, and closes transactions in requests, jobs,
  CLI commands, and tests?
- Is the current app-context teardown commit policy retained or changed? How do
  handled failures and error responses affect persistence?
- What does autoflush mean for queries and validation? What happens after a flush
  raises an integrity error?
- Do timestamps and post-commit hooks work across multiple flushes and rollback?

**Validation and callbacks**

- Is validation an explicit application operation, a service, or a session hook?
- Start by testing `save()` as validation plus add/flush, returning a success
  boolean and not committing the surrounding transaction. Define `create()`,
  `update()`, and `destroy()` consistently, including invalid `create()` results.
  This is a candidate contract, not an assumption that it is safe or complete.
- Does saving one object flush unrelated pending objects? What does validation
  cover in that case, including objects reached through relationship cascades?
- A failed validation on a persistent instance leaves SQLAlchemy tracking its
  edits. How are those edits prevented from being flushed by a later query,
  another object's `save()`, or the final commit? Demonstrate a policy without
  introducing a parallel change store or silently losing form input.
- What guarantees hold when users call `session.add()` or `flush()` directly?
  Distinguish framework-operation callbacks from any session-wide guarantees;
  native interoperability does not automatically mean identical lifecycle hooks.
- Which callbacks map cleanly to SQLAlchemy events, and which should be redesigned
  or removed? Do not promise that direct ORM/bulk operations run model callbacks
  unless demonstrated.
- Keep database constraints authoritative; validation does not prevent races.

**Mapping and application isolation**

- Can model modules be imported without connecting to a database, including before
  initial migrations? Native declarations should not require runtime reflection.
- When are all model modules imported and relationships configured? Test cyclic
  imports and string relationship targets. Eager mapping configuration is an
  option, not a regression to hide behind a new lazy-loading abstraction.
- Can the same mapped classes safely serve two application engines and separate
  sessions when their schemas match?
- What happens with different model sets, incompatible schemas, and failed mapper
  configuration? Distinguish session/engine isolation from registry isolation.
- Document limits instead of using private mapper mutation or global mapper resets.

**Schema workflow**

- Initially maintain explicit declarations in `app/schema.py`; do not make
  database reflection or automatic schema regeneration a prerequisite. If later
  generating the module from the database is desirable, treat that as a separate
  tooling experiment, not runtime model discovery.
- Keep schema declarations independent of application model imports; use deferred
  relationship targets to avoid circular imports. Demonstrate deterministic model
  discovery/configuration and avoid registering unmapped schema classes as models.
- Does changing the schema module require a process restart? Prefer a clear fresh
  mapping lifecycle over mutating already-published mappings.
- How do explicit declarations and Alembic migrations stay aligned? Demonstrate
  generated metadata discovery and review of autogenerate output if used.
- What remains manual for renames, data migrations, and unsupported schema changes?
- Can startup and database CLI commands work against an empty/unmigrated database
  without trying to query or reflect application tables?

## Phase 3: check representative integrations

Once the core slice works, exercise one authentication flow and one attachment
flow. Inventory the remaining integration costs rather than porting everything.

Pay particular attention to invalid form values: native mapped attributes and
SQLAlchemy type handling do not automatically reproduce the current coercion and
pending-change behavior. Decide where raw form input belongs.

Demonstrate that sensitive fields remain excluded from serialization and that
post-commit work is not dispatched for rolled-back writes.

## Phase 4: compare and decide

Record evidence for both the prototype and current approach:

| Area | Evidence to collect |
| --- | --- |
| Application ergonomics | Rails-like CRUD/forms, SQLAlchemy field declarations, native interoperability |
| Framework complexity | Machinery actually removable versus newly required machinery |
| State and identity | Same row yields the same object within a session; coherent changes/rollback |
| Relationships | Native loading, assignment, cascades, and query counts |
| Tooling | Accepted dynamic-field typing/completion limits, tracebacks, optional stub opportunities |
| Lifecycle | Empty-database commands, transactions, multiple apps, mapper failures |
| Compatibility | Lost behaviors, generated-code changes, integration porting effort |
| Schema maintenance | Duplication and drift risks between declarations and migrations |

Do not use framework line count or a microbenchmark as the sole success measure.
A small application-code increase can be worthwhile if it removes substantial
framework machinery, but moving complexity into controllers is not a win.

### Proceed if

- Behavior-only application models receive SQLAlchemy schema declarations by name
  during class creation and are ordinary mapped instances. Abstract bases and
  lookup/configuration failures have clear, tested behavior.
- Rails-like methods remain pleasant for routine work, and native queries/session
  operations interoperate without wrappers, state synchronization, or conversion.
- Reflection, wrapper, custom change-tracking, and association machinery can
  materially shrink. The retained query/persistence facade is substantially
  simpler than the machinery it replaces.
- Validation/forms, transactions, and application isolation have understandable,
  tested semantics.
- Representative integrations remain practical and the compatibility costs are
  explicit and acceptable.

### Revise or stop if

- Preserving the desired UX requires recreating the current parallel state system.
- Session behavior makes routine application code surprising or fragile.
- Required isolation cannot be achieved with a maintainable public-API design.
- Generator/schema duplication and integration costs outweigh the simplification.

## Only after a proceed decision

Write a separate implementation plan based on the prototype's evidence:

1. Specify the schema-module contract, automatic name-based composition rules,
   Rails-like facade, native interoperability boundaries, accepted tooling limits,
   and deliberate breaking changes.
2. Choose a replacement/release strategy; do not assume indefinite dual support.
3. Plan changes to database integration, generators, migrations, forms, callbacks,
   authentication, attachments, and testing helpers.
4. Port representative applications and public contract tests before removing old
   machinery; document changed semantics instead of weakening tests silently.
5. Update documentation and migration guidance, then remove obsolete internals.

Run focused tests during the experiment. Before adopting a production migration,
run the full relevant suite, generated-application checks, browser tests where
applicable, and supported backend coverage. Keep the project's existing lint,
format, scoped typing, and CI requirements intact.

## Exploration deliverables

- Runnable class-creation spike and isolated application prototype, with focused
  tests and reproduction commands.
- Same-name schema lookup/composition rules, failure cases, and evidence that only
  the application classes are mapped.
- Side-by-side current/hybrid application examples, with explicit-inheritance and
  native-only baselines.
- Recorded typing/completion trade-offs and optional tooling improvements.
- Contract/compatibility matrix and answers to the lifecycle/isolation questions.
- List of removable internals, replacement machinery, and remaining unknowns.
- A written proceed, revise, or stop recommendation. No migration is assumed.
