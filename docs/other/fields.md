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

Model, resource, and scaffold generators also accept `avatar:attachment` for a
single file and `documents:attachments` for multiple files. These declare
attachments rather than database columns. Run `flask attachments:install`
before migrating. See [Attachments](attachments.md).
