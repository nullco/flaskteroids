from flaskteroids.inflector import Inflector


def camel_to_snake(text: str) -> str:
    return Inflector().underscore(text)


def snake_to_camel(text: str) -> str:
    return Inflector().camelize(text)


def pluralize(text: str) -> str:
    return Inflector().pluralize(text)


def singularize(text: str) -> str:
    return Inflector().singularize(text)
