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
