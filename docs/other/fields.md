# Fields

Migration, model, resource, and scaffold generators accept these field types:

| Type | Generator argument |
| --- | --- |
| Text | `text` |
| String (255 characters) | `string` or `str` |
| Integer | `integer` or `int` |
| Float | `float` |
| Boolean | `boolean` or `bool` |
| Date and time | `datetime` |
| Date | `date` |
| Time | `time` |
| JSON | `json` |

```sh
flask generate model Post title:string! content:text published:boolean
flask db:prepare
```

`!` makes a database column non-nullable. `author:references` (or
`author:belongs_to`) adds a required foreign key and a `belongs_to` rule in a
generated model. Database constraints do not replace user-facing validation;
add `validates(...)` when invalid input should return errors rather than a
native constraint exception.

Generators use SQLAlchemy type factories. They do not maintain a second input
casting API. Migrations define the database; the generated `app/schema.py`
snapshot supplies mapped column types. Do not edit it to change a field.

## Model casting and raw input

Casting happens at model assignment, not only in forms or at database bind time.
Scalar input remains staged until saved. Read it through normal attributes, and
inspect original input with `read_attribute_before_type_cast(name)`.

- String/text values stringify ordinary input; `None` remains `None`.
- Integers accept numeric strings and numeric prefixes (`"12extra"` reads as `12`).
  Blank input reads as `None`; nonnumeric strings read as zero but serialize as
  null. Add numericality validation to reject malformed original input.
- Float/decimal values cast numeric strings; blank input reads as `None`.
- Booleans cast `""` to `None`. False values include `False`, `0`, `"0"`, `"f"`,
  `"F"`, `"false"`, `"FALSE"`, `"off"`, and `"OFF"`; other non-null values are true.
- Dates/times accept ISO-formatted strings and corresponding Python values.
  Invalid date/time strings read as `None`; the original input is retained for
  validation and form redisplay.
- JSON values retain their Python structure and native SQLAlchemy serialization.
  Supported backend-specific types use SQLAlchemy's native database handling.

```python
post = Post.new(word_count="12extra")
assert post.word_count == 12
assert post.read_attribute_before_type_cast("word_count") == "12extra"
# validates("word_count", numericality={"only_integer": True}) rejects this input.
```

## Nulls and defaults

Explicit `None` remains null for ordinary scalar columns, even when a server
default exists. An omitted value can instead use the default. Simple literal
server defaults are decoded for new model instances without database I/O;
server functions and computed values populate on flush. Put persistent defaults
in migrations; Python-side default functions cannot be recovered from a snapshot.

JSON's default serialization stores explicit `None` as JSON `null`, which reads
back as `None`. JSON `null` is distinct from SQL `NULL`; an SQL `IS NULL` predicate
does not necessarily match it. Primary-key generation remains native.

## Attachments

Model, resource, and scaffold generators accept `avatar:attachment` for a single
file and `documents:attachments` for multiple files. These declare attachments,
not scalar columns. Run `flask attachments:install`, then migrate and regenerate
the snapshot through `flask db:migrate`. See [Attachments](attachments.md).
