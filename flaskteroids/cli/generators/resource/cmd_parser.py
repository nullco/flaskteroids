import re
from flaskteroids.inflector import inflector
from flaskteroids.cli.generators import cmd_parser
from flaskteroids.cli.generators.fields import field_pattern, association_pattern


class _ResourceCommand:
    pattern = re.compile(r'([a-z_]+)')
    args = {
        'fields': field_pattern,
        'reference': association_pattern
    }

    @classmethod
    def parse(cls, cmd, args):
        matcher = cmd_parser.CommandArgsMatcher(cls.pattern, cls.args)
        cmd_match = matcher.match_cmd(cmd)
        args_matches = matcher.match_args(args)
        model = inflector.camelize(cmd_match.group())
        controller = inflector.pluralize(model)
        return {
            'cmd': 'resource',
            'model': model,
            'controller': controller,
            'plural': inflector.pluralize(cmd_match.group()),
            'fields': [
                {'name': m.group(1), 'type': m.group(2)}
                for m in args_matches['fields']
            ],
            'references': [
                {'name': m.group(1), 'type': m.group(2)}
                for m in args_matches['reference']
            ]
        }


def parse(cmd, args):
    return cmd_parser.parse(cmd, args, [_ResourceCommand])
