import re
from flaskteroids.cli.generators import cmd_parser
from flaskteroids.str_utils import pluralize, snake_to_camel

class _MailerCommand:
    pattern = re.compile(r'([a-z_]+)')

    @classmethod
    def parse(cls, cmd, _):
        matcher = cmd_parser.CommandArgsMatcher(cls.pattern)
        match = matcher.match_cmd(cmd)
        if match:
            mailer = snake_to_camel(match.group())
            return {
                'cmd': 'mailer',
                'snake': match.group(),
                'snake_plural': pluralize(match.group()),
                'camel': mailer,
                'camel_plural': pluralize(mailer)
            }


def parse(cmd, args):
    return cmd_parser.parse(cmd, args, [_MailerCommand])
