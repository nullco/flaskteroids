import re
from cucurbit.cli.generators import cmd_parser
from cucurbit.inflector import inflector


class _MailerCommand:
    pattern = re.compile(r'([a-z_]+)')

    @classmethod
    def parse(cls, cmd, _):
        matcher = cmd_parser.CommandArgsMatcher(cls.pattern)
        match = matcher.match_cmd(cmd)
        if match:
            mailer = inflector.camelize(match.group())
            return {
                'cmd': 'mailer',
                'snake': match.group(),
                'snake_plural': inflector.pluralize(match.group()),
                'camel': mailer,
                'camel_plural': inflector.pluralize(mailer)
            }


def parse(cmd, args):
    return cmd_parser.parse(cmd, args, [_MailerCommand])
