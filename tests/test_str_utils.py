import pytest

from flaskteroids.str_utils import camel_to_snake, pluralize, singularize, snake_to_camel


@pytest.mark.parametrize('input, expected', [
    ('auto', 'autos'),
    ('Bike', 'Bikes'),
])
def test_pluralize(input, expected):
    assert pluralize(input) == expected


@pytest.mark.parametrize('input, expected', [
    ('Auto', 'auto'),
    ('UserController', 'user_controller'),
    ('UserPostsController', 'user_posts_controller'),
])
def test_camel_to_snake(input, expected):
    assert camel_to_snake(input) == expected


@pytest.mark.parametrize('input, expected', [
    ('auto', 'Auto'),
    ('user_controller', 'UserController'),
    ('user_posts_controller', 'UserPostsController'),
])
def test_snake_to_camel(input, expected):
    assert snake_to_camel(input) == expected


@pytest.mark.parametrize('input, expected', [
    ('autos', 'auto'),
    ('Bikes', 'Bike'),
    ('auto', 'auto')
])
def test_singularize(input, expected):
    assert singularize(input) == expected
