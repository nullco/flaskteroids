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
        parsed = c.parse(cmd, args)
        if parsed:
            return parsed
    raise Exception('Command not found')


class CommandArgsMatcher:

    def __init__(self, cmd_pattern, args_patterns):
        self._cmd_pattern = cmd_pattern
        self._args_patterns = args_patterns

    def match(self, cmd, args):
        match = self._cmd_pattern.match(cmd)
        if match:
            if not self._args_patterns and args:
                raise Exception('Arguments not expected')
            args_matches = defaultdict(lambda: [])
            for arg in args:
                for k, p in self._args_patterns.items():
                    amatch = p.match(arg)
                    if amatch:
                        args_matches[k].append(amatch)
            if not args_matches:
                raise Exception('Argument not matching expected format')
            return match, args_matches
