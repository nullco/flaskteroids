import sqlalchemy as sa


def _cast_or_none(fn, value):
    try:
        return fn(value)
    except ValueError:
        return None


class Text:
    column_type = sa.Text
    primitive_type = str

    @classmethod
    def cast(cls, value):
        return value


class String:
    column_type = sa.String
    primitive_type = str

    @classmethod
    def cast(cls, value):
        return value


class Integer:
    column_type = sa.Integer,
    primitive_type = int

    @classmethod
    def cast(cls, value):
        return _cast_or_none(int, value)


class Float:
    column_type = sa.Float,
    primitive_type = float

    @classmethod
    def cast(cls, value):
        return _cast_or_none(float, value)


class Boolean:
    column_type = sa.Boolean
    primitive_type = bool

    @classmethod
    def cast(cls, value):
        false_values = {'false', 'f', 0, '0', False, None, ''}
        if value in false_values:
            return False
        return True


class Json:
    column_type = sa.JSON
    primitive_type = dict

    @classmethod
    def cast(cls, value):
        return value


fields = {
    'text': Text,
    'string': String,
    'str': String,
    'interger': Integer,
    'int': Integer,
    'boolean': Boolean,
    'bool': Boolean,
}


def get(column_type):
    for f in fields.values():
        if isinstance(column_type, f.column_type):
            return f
    raise ValueError(f'Columm type <{column_type}> is not supported yet')
