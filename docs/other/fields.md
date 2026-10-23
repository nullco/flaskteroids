# Fields

Use `name:type` arguments when generating a migration, model, resource, or
scaffold. For example, `title:string` creates a string column named `title`.

## Column types

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
bin/flask generate model Post title:string! content:text published:boolean
bin/flask db:prepare
```

## Required columns and references

`!` makes a database column non-nullable, so it cannot store SQL NULL.

`author:references` (or `author:belongs_to`) adds a required foreign key and a
`belongs_to(...)` declaration inside the generated model class. Database constraints do not replace
user-facing validation; add `validates(...)` inside the model class when invalid
input should return errors rather than a native constraint exception.

Change column definitions through migrations, not by editing the generated
`db/schema.py`. The snapshot supplies model column types using SQLAlchemy's type
system; there is no separate generator casting API.

## Model casting and raw input

When you assign a model attribute, Flaskteroids converts the value to its column
type. This is **casting**, not validation: a value may convert successfully and
still be invalid for your application. Changes stay pending until saved.

Read the converted value normally, or inspect the original input with
`read_attribute_before_type_cast(name)`.

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
# For a Post model with an integer word_count column:
post = Post.new(word_count="12extra")
assert post.word_count == 12
assert post.read_attribute_before_type_cast("word_count") == "12extra"
# Add validates("word_count", numericality={"only_integer": True}) to reject it.
```

## Nulls and defaults

Omitting a value lets a database default apply. Explicitly assigning `None`
stores null for ordinary scalar columns, even when a default exists.

Simple literal database defaults are available on new models without a query.
Database functions and computed values populate on flush. Put persistent defaults
in migrations; Python default functions cannot be recovered from a snapshot.

JSON's default serialization stores explicit `None` as JSON `null`, which reads
back as `None`. JSON `null` is distinct from SQL `NULL`; an SQL `IS NULL` predicate
does not necessarily match it. Primary-key generation remains native.

## Rich text

Model, resource, and scaffold generators accept `content:rich_text`. This generates
`has_rich_text("content")`, not a column on the owner. Scaffolds include a Trix
editor, safe rendering, and permitted parameters. Run `bin/flask rich_text:install`,
then `bin/flask db:migrate`. See [Rich text](rich_text.md).

## Attachments

Model, resource, and scaffold generators accept `avatar:attachment` for a single
file and `documents:attachments` for multiple files. These declare attachments,
not scalar columns. Run `bin/flask attachments:install`, then apply the migrations
with `bin/flask db:migrate`. See [Attachments](attachments.md).
