# Model basics

Models represent your application's data and the rules for working with it.
Use them to query records, validate input, manage associations, and save changes.

Define columns in database migrations and behavior in model classes. Flaskteroids
reads column definitions from the generated `db/schema.py`; you do not repeat
them in your models. SQLAlchemy is available for advanced queries and integration,
but ordinary model work does not require managing a session.

After reading this guide, you will know how to:

- Generate a model and apply its database migration.
- Create, find, update, and delete records.
- Handle invalid input and group saves in a transaction.

The examples use an `Author` and its `Post` records. Run commands from your
application root. If you are new to Flaskteroids, start with
[Getting started](../getting_started.md).

## Define models and migrate

Application models inherit from the generated abstract base:

```python
# app/models/application_model.py
from flaskteroids.model import Model


class ApplicationModel(Model):
    __abstract__ = True
```

Generate models and their migrations from your application directory:

```sh
bin/flask generate model Author name:string
bin/flask generate model Post title:string author:references
bin/flask db:prepare
```

Add behavior to the generated classes:

```python
# app/models/author.py
from app.models.application_model import ApplicationModel
from flaskteroids.model import has_many, validates


class Author(ApplicationModel):
    has_many("posts", dependent="destroy")
    validates("name", presence=True)

    def greeting(self):
        return f"Hello, {self.name}"
```

```python
# app/models/post.py
from app.models.application_model import ApplicationModel
from flaskteroids.model import belongs_to, validates


class Post(ApplicationModel):
    belongs_to("author")
    validates("title", presence=True)
```

`Post` uses the `posts` table by convention. Set
`__table_name__ = "legacy_posts"` to use a different table.

### The schema snapshot

Successful `db:migrate`, `db:prepare`, and `db:rollback` commands regenerate
`db/schema.py` from the selected database. **Commit the snapshot, but do not edit
it by hand.** To refresh it without migrating, run `bin/flask db:schema:dump`.
Restart servers and workers after migrations so they load the new definitions.
See [database commands](../other/cli.md#database-preparation).

The snapshot describes tables, columns, keys, constraints, indexes, and server
defaults, including tables with no model class. It does not contain validations,
associations, or other model behavior.

## Queries

Use `find()` when you have a record's ID:

```python
post = Post.find(1)
```

If the record is absent, `find()` raises `RecordNotFoundException`. To look up
a record by an attribute and receive `None` when it is absent, use `find_by()`:

```python
post = Post.find_by(title="First")
```

### Filter and order records

Build a query with `where()`, then add ordering or pagination:

```python
posts = Post.where(title="First")
page = posts.order(title="asc").limit(20).offset(40)
for post in page:
    print(post.title)
```

Queries are **lazy**: iteration loads the records. Methods such as `first()`
and `count()` also run the query. `all()` returns a query, not a list; use
`list(Post.all())` when you need a list.

Queries return new scopes rather than changing the original query. Keep the
result when you add a filter or ordering. Iterating again runs the query again.

By default, records are ordered by ascending primary key. Limits and offsets
apply to `count()` too. For an expression-based filter, use model attributes:

```python
posts = Post.where(Post.title.ilike("a%"))
```

To preload related records, see
[Load associations together](associations.md#load-associations-together).

## Assignment, validation, and persistence

Build a record, then check the result of saving it:

```python
author = Author.create(name="Ada")
post = Post.new(title="First", author=author)
if post.save():
    identifier = post.id
else:
    messages = post.errors.full_messages()
```

`create()` builds and saves in one call. It returns the record even if validation
fails. `update()` assigns attributes and returns whether saving succeeded:

```python
post = Post.create(title="", author=author)
assert post.errors
assert post.update(title="Fixed")
```

### Unsaved changes

Assigning a scalar attribute changes what you read on that object, but does not
save it to the database until a successful save.
Invalid input and its errors remain available for correction and form redisplay.
Another object's save or a later commit does not accidentally save these edits.
This also applies to valid edits you have not explicitly saved.

- `reload()` loads saved state and discards pending scalar input and errors.
- `discard_changes()` discards pending scalar input without refreshing saved state.

## Validate records

Validations express rules that input must satisfy before a record can be saved.
For example, update the title validation in `app/models/post.py`:

```python
    validates("title", presence=True, length={"minimum": 3, "maximum": 100})
```

Keep the existing imports and association declaration. Now a blank or overly
short title prevents saving. You can also check a record without saving it:

```python
post = Post.new(title="", author=author)
if not post.is_valid():
    messages = post.errors.full_messages()
```

The record keeps its submitted input and errors. Correct the input and save
again, or render the same object in a form so the user can correct it.
See [Forms](../other/forms.md#redisplay-validation-errors).

Converting input to a column type is not validation. For numeric input, use a
numericality validation to reject malformed values rather than relying on
conversion alone. See [Fields](../other/fields.md#model-casting-and-raw-input).

## Defaults

Put persistent defaults in migrations. Simple literal database defaults are
available on new objects without a query. Database functions, computed columns,
and generated IDs become available when the database writes the record.
Explicit `None` does not request a default; JSON retains its native JSON-null
behavior.

`save()` maintains declared `created_at` and `updated_at` attributes. Native
writes do not run this timestamp behavior automatically.

Python default functions cannot be recovered from the database snapshot. Use
assignment or initialization callbacks for application-side defaults, rather
than `Column.default` definitions or edits to `db/schema.py`.

## Transactions

A standalone `save()`, `create()`, or `update()` **commits before returning**.
Associated rows saved by the operation share its transaction. A failure or halted
callback rolls back that operation, not earlier successful standalone saves.

Use an explicit transaction when several operations must succeed together:

```python
with Author.transaction():
    author = Author.create(name="Ada")
    post = Post.create(title="First", author=author)
    if post.errors:
        raise ValueError("Post is invalid")
# Both writes commit here; an exception escaping the block rolls both back.
```

Saves inside the block join its transaction without committing individually.
**A `False` save result does not abort the block**; raise an exception when the
whole group should roll back. Transactions cover all models in the application,
not just the class used to open the block.

Nested `Model.transaction()` blocks join the outer transaction by default. Use
`requires_new=True` for a savepoint. Catch a failure outside the inner block if
the outer operation should continue. After-commit callbacks wait for the outer
commit, not savepoint release.

`save(validate=False)` skips validation, not database constraints. Integrity
errors propagate as exceptions rather than model errors. Standalone failures
clean up their transaction. After a database error inside an explicit transaction,
roll back/recover that transaction before further writes. An earlier query does
not turn a later standalone save into an explicit transaction.

## Delete records

Call `destroy()` to delete a record:

```python
post = Post.find(1)
if post.destroy():
    print("Post removed")
```

Destruction runs callbacks and commits before returning, unless it joins an
explicit transaction. A callback can reject it: `destroy()` then returns `False`
and rolls back that standalone operation. Inside a transaction, raise an
exception if rejection should roll back the whole group.

For deleting related records, see [Association deletion](associations.md#deletion).

## Associations

A model can belong to another record or have a collection of related records.
For example, an author has many posts, and each post belongs to an author.

Read [Model associations](associations.md) to declare relationships, build records
through them, and save related form input.

## Callbacks

Use callbacks for behavior that should run whenever a model is saved or
destroyed. Use `after_commit` for external work, such as scheduling email after a
successful save. See [Model callbacks](callbacks.md) for examples.

## Passwords

Use the [authentication generator](../other/cli.md#authentication) for a complete
login and password-reset workflow. It sets up `has_secure_password()` so the
database stores a digest, not a plaintext password.

Follow [Add login and product images](../tutorial/authentication_and_uploads.md)
for a walkthrough. Do not log password input, digests, or reset tokens.

## Encrypted attributes

Use `encrypts("notes")` for randomized string/text encryption. Use
`encrypts("email", deterministic=True, downcase=True)` when equality lookups are
needed. Assignment, validations, and forms still work with plaintext; database
storage uses ciphertext.

Rich-text encryption uses the same service and dedicated keys. See
[Attribute encryption](encryption.md) for setup, queries, key rotation, and limits.

## Temporary attributes and serialization

For a value that should not be saved, declare a class default, a property with a
setter, or a private cache name. Initialize mutable caches per instance. Unknown
public assignments raise `AttributeError`, and framework methods/metadata cannot
be replaced through assignment.

Temporary values are not automatically saved or serialized. Repeated lookups in
one session return the same object, including its temporary state.

Default JSON includes mapped scalar attributes and staged values, but excludes
authentication secrets and virtual fields. Override `__json__()` for a custom
response, or add names to the `_serialization_exclude` set. Form values are
independent of JSON serialization. Ordinary editors/type checkers generally
cannot infer dynamically mapped fields.

## Class-body declarations

Import declarations such as `validates`, `belongs_to`, and `before_save` at
module scope, then call them directly inside the model class. Callbacks can name
methods defined later in that class. Put shared declarations in an abstract
base model or a mixin.

## Native SQLAlchemy and transactions

SQLAlchemy is available for advanced queries and integrations. Ordinary model
work should use the framework's query and persistence methods.

Native and bulk writes bypass framework validations and save callbacks. They
also need an explicit transaction or commit; leaving an application context
rolls back unfinished native work. A framework save can flush native pending
changes, so use explicit transaction boundaries when mixing the two APIs.

## Next steps

- [Model associations](associations.md) — work with related records.
- [Model callbacks](callbacks.md) — attach behavior to a record's lifecycle.
- [Forms](../other/forms.md) — accept input and redisplay validation errors.
- [Fields](../other/fields.md) — choose column types and understand casting.
