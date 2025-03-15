import re
from flaskteroids.generators import cmd_parser


_cmd_patterns = {
    'create_table': re.compile(r'create_([a-z]+)'),
    'add_columns_to_table': re.compile(r'add_([a-z_]+)_to_([a-z]+)'),
    'remove_columns_from_table': re.compile(r'remove_([a-z_]+)_from_([a-z]+)'),
}


def parse(cmd):
    return cmd_parser.parse(cmd, _cmd_patterns)
