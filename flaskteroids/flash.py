from flask import flash as _flash, get_flashed_messages


class Flash:

    def __setitem__(self, key, value):
        _flash(value, key)

    def __getitem__(self, key):
        return self.messages.get(key, '')

    @property
    def messages(self):
        flashed_messages = dict()
        for category, message in get_flashed_messages(with_categories=True):
            flashed_messages[category] = message
        return flashed_messages


flash = Flash()
