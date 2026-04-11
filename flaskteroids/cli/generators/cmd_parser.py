from collections import defaultdict
from flaskteroids.inflector import inflector


def parse(cmd, args, cmds):
    normalized_cmd = inflector.underscore(cmd)
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
        not_matched = []
        for arg in args:
            for k, p in self._args_patterns.items():
                amatch = p.match(arg)
                if amatch:
                    args_matches[k].append(amatch)
                    break
            else:
                not_matched.append(arg)
        if not_matched and self._args_patterns:
            raise ValueError(f'Invalid arguments: {" ".join(not_matched)}')
        return args_matches
