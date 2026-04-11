import re
from flaskteroids.inflector import inflector
from flaskteroids.cli.generators import cmd_parser
from flaskteroids.cli.generators.fields import field_pattern, association_pattern


class _ScaffoldCommand:
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
        model_ref = cmd_match.group()
        models_ref = inflector.pluralize(model_ref)
        controller = inflector.pluralize(model)
        return {
            'cmd': 'scaffold',
            'model': model,
            'model_ref': model_ref,
            'models_ref': models_ref,
            'controller': controller,
            'singular': cmd_match.group(),
            'plural': inflector.pluralize(cmd_match.group()),
            'fields': [
                {'name': m.group(1), 'type': m.group(2)}
                for m in args_matches['fields']
            ],
            'references': [
                {'name': inflector.foreign_key(m.group(1)), 'type': m.group(2)}
                for m in args_matches['reference']
            ]
        }


def parse(cmd, args):
    return cmd_parser.parse(cmd, args, [_ScaffoldCommand])
