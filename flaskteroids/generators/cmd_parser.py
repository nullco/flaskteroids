import re


def parse(cmd, cmd_patterns):
    normalized_cmd = _normalize(cmd)
    return {
        'cmd': cmd,
        'normalized_cmd': normalized_cmd,
        'match': _match(normalized_cmd, cmd_patterns)
    }


def _normalize(cmd):
    # Makes commands in CamelCase as snake_case
    return re.sub(r'(?<!^)(?=[A-Z])', '_', cmd).lower()


def _match(cmd, cmd_patterns):
    for k, p in cmd_patterns.items():
        match = p.match(cmd)
        if match:
            return {
                'action': k,
                'captured_groups': match.groups()
            }
    raise Exception('Command not found')
