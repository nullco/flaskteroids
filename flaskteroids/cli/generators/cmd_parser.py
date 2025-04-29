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
