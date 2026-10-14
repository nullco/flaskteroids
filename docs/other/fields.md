# Fields

Migration, model, resource, and scaffold generators accept these field types:

| Type | Generator argument |
| --- | --- |
| Text | `text` |
| String | `string` or `str` |
| Integer | `integer` or `int` |
| Float | `float` |
| Boolean | `boolean` or `bool` |
| Date and time | `datetime` |
| Date | `date` |
| Time | `time` |
| JSON | `json` |

For example:

```sh
flask generate model Post title:string content:text published:boolean
```

## Null values

Assigning `None` to any supported column type preserves `None` during model
casting. String and text fields do not turn it into `"None"`; boolean fields do
not turn it into `False`. Numeric and JSON fields accept it without conversion
errors. Ordinary non-null conversions are unchanged, including the existing
boolean conversion of an empty string to `False`.

For ordinary nullable non-JSON columns, a saved `None` becomes SQL `NULL`.
Insert defaults still follow the underlying column configuration; casting does
not override them. The default JSON column type instead serializes an explicit
`None` as JSON `null`, which also reads back as `None`.
JSON `null` is distinct from SQL `NULL`; do not assume an SQL `IS NULL` predicate
matches it. This change does not alter JSON database serialization.

## Attachments

Model, resource, and scaffold generators also accept `avatar:attachment` for a
single file and `documents:attachments` for multiple files. These declare
attachments rather than database columns. Run `flask attachments:install`
before migrating. See [Attachments](attachments.md).
