import re


def camel_to_snake(text: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', text).lower()


def snake_to_camel(text: str) -> str:
    return ''.join([t.title() for t in text.split('_')])


def pluralize(text: str) -> str:
    if text.endswith('s'):
        return text
    return f'{text}s'


def singularize(text: str) -> str:
    if not text.endswith('s'):
        return text
    return text[:-1]
