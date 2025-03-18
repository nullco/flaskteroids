import re


def parse(cmd, args, cmds):
    normalized_cmd = _normalize(cmd)
    return {
        'cmd': cmd,
        'normalized_cmd': normalized_cmd,
        'parsed': _parse(normalized_cmd, args, cmds)
    }


def _normalize(cmd):
    # Makes commands in CamelCase as snake_case
    return re.sub(r'(?<!^)(?=[A-Z])', '_', cmd).lower()


def _parse(cmd, args, cmds):
    for c in cmds:
        parsed = c.parse(cmd, args)
        if parsed:
            return parsed
    raise Exception('Command not found')
