from collections import defaultdict
from flaskteroids import str_utils


def parse(cmd, args, cmds):
    normalized_cmd = str_utils.camel_to_snake(cmd)
    return {
        'cmd': cmd,
        'normalized_cmd': normalized_cmd,
        'parsed': _parse(normalized_cmd, args, cmds)
    }


def _parse(cmd, args, cmds):
    for c in cmds:
        try:
            parsed = c.parse(cmd, args)
            if parsed:
                return parsed
        except ValueError:
            continue
    raise ValueError('Command not found')


class CommandArgsMatcher:

    def __init__(self, cmd_pattern, args_patterns=None):
        self._cmd_pattern = cmd_pattern
        self._args_patterns = args_patterns or {}

    def match_cmd(self, cmd):
        match = self._cmd_pattern.match(cmd)
        if not match:
            raise ValueError('Command not matching expected format')
        return match

    def match_args(self, args):
        if not self._args_patterns and args:
            raise ValueError('Arguments not expected')
        args_matches = defaultdict(lambda: [])
        for arg in args:
            for k, p in self._args_patterns.items():
                amatch = p.match(arg)
                if amatch:
                    args_matches[k].append(amatch)
        if not args_matches and self._args_patterns:
            raise ValueError('Argument not matching expected format')
        return args_matches
