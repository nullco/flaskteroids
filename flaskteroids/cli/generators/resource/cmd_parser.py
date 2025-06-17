import re
from flaskteroids.cli.generators import cmd_parser
from flaskteroids.str_utils import pluralize, snake_to_camel

_field_types = ['int', 'str', 'text', 'float', 'bool', 'json', 'references', 'belongs_to']
_field_types_pattern = fr'{"|".join(k for k in _field_types)}'
_fields_pattern = re.compile(fr'^([a-z_]+):({_field_types_pattern})(!?)$')


class _ResourceCommand:
    pattern = re.compile(r'([a-z_]+)')
    args = {
        'fields': _fields_pattern
    }

    @classmethod
    def parse(cls, cmd, args):
        matcher = cmd_parser.CommandArgsMatcher(cls.pattern, cls.args)
        match = matcher.match(cmd, args)
        if match:
            cmd_match, args_matches = match
            model = snake_to_camel(cmd_match.group())
            controller = pluralize(model)
            return {
                'cmd': 'resource',
                'model': model,
                'controller': controller,
                'plural': pluralize(cmd_match.group()),
                'fields': [
                    {'name': m.group(1), 'type': m.group(2)}
                    for m in args_matches['fields']
                ]
            }


def parse(cmd, args):
    return cmd_parser.parse(cmd, args, [_ResourceCommand])
