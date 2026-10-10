import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime
from flaskteroids.model import Model, validates
from flaskteroids.rules import rules


@pytest.fixture(autouse=True)
def init(init_models):
    init_models(Base, [
        (UserBase, User),
    ])


Base = declarative_base()


class UserBase(Base):
    __tablename__ = 'users'

    id = Column(Integer(), primary_key=True, autoincrement=True)
    username = Column(String())
    age = Column(Integer())
    last_login = Column(DateTime())


class ProductBase(Base):
    __tablename__ = 'products'

    id = Column(Integer(), primary_key=True, autoincrement=True)
    quantity = Column(Integer())
    created_at = Column(DateTime())
    updated_at = Column(DateTime())
    expires_at = Column(DateTime())


@rules(
    validates('username', presence=True),
)
class User(Model):
    pass


class TestModelCRUD:

    def test_new(self):
        user = User.new(username='one')
        assert user.username == 'one'

    def test_create(self):
        user = User.create(username='one')
        assert user.id

    def test_edit(self):
        user = User.create(username='one')
        user.username = 'two'
        user.save()

        user = User.find(id=user.id)
        assert user.username == 'two'

    def test_save(self):
        user = User.new(username='one')
        assert user.save()

    def test_save_with_errors(self):
        user = User.new()
        assert not user.save()
        assert user.errors
        assert user.errors.count == 1

    def test_find(self):
        user = User.create(username='one')
        assert User.find(id=user.id)

    def test_all(self):
        User.create(username='one')
        User.create(username='two')
        User.create(username='three')
        assert len(list(User.all())) == 3

    def test_count_first_and_last(self):
        first = User.create(username='one')
        last = User.create(username='two')

        assert User.count() == 2
        assert User.first().id == first.id
        assert User.last().id == last.id

    def test_reload(self):
        user = User.create(username='one')
        user.username = 'two'

        assert user.reload().username == 'one'

    def test_find_by(self):
        User.create(username='one')
        User.create(username='two')
        User.create(username='three')
        one = User.find_by(username='one')
        assert one
        assert one.username == 'one'

    @pytest.mark.parametrize('query_factory, expected_count', [
        (lambda: User.username == 'one', 1),
        (lambda: User.username == 'two', 1),
        (lambda: User.username.in_(['one', 'three']), 2),
        (lambda: User.age >= 25, 2),
        (lambda: User.last_login < datetime(2021, 1, 1), 1),
        (lambda: (User.age < 30) & (User.last_login >= datetime(2021, 1, 1)), 1),
    ])
    def test_where(self, query_factory, expected_count):
        User.create(username='one', age=30, last_login=datetime(2022, 5, 20))
        User.create(username='two', age=25, last_login=datetime(2021, 6, 15))
        User.create(username='three', age=15, last_login=datetime(2020, 1, 1))
        query = query_factory()
        users = User.where(query).all()
        assert len(list(users)) == expected_count


class TestModelPagination:

    @pytest.fixture
    def users(self):
        return [User.create(username=f'user-{i}', age=i % 2) for i in range(5)]

    @pytest.mark.parametrize('query_factory, expected_indexes', [
        (lambda: User.limit(2).order(id='asc'), [0, 1]),
        (lambda: User.offset(2).order(id='asc'), [2, 3, 4]),
        (lambda: User.order(id='asc').limit(2).offset(2), [2, 3]),
        (lambda: User.offset(2).limit(2).order(id='asc'), [2, 3]),
        (lambda: User.order(id='desc').limit(2).offset(1), [3, 2]),
        (lambda: User.where(age=0).order(id='asc').limit(1).offset(1), [2]),
        (lambda: User.limit(1).offset(1).where(age=0).order(id='asc'), [2]),
        (lambda: User.all().order(id='asc').limit(2).offset(4), [4]),
        (lambda: User.limit(0), []),
        (lambda: User.offset(0).order(id='asc'), [0, 1, 2, 3, 4]),
        (lambda: User.offset(5).limit(2), []),
        (lambda: User.limit(10).order(id='asc'), [0, 1, 2, 3, 4]),
        (lambda: User.limit(1).limit(3).order(id='asc'), [0, 1, 2]),
        (lambda: User.offset(1).offset(3).order(id='asc'), [3, 4]),
        (lambda: User.limit(1).limit(None).order(id='asc'), [0, 1, 2, 3, 4]),
        (lambda: User.offset(3).offset(None).order(id='asc'), [0, 1, 2, 3, 4]),
    ])
    def test_pagination(self, users, query_factory, expected_indexes):
        query = query_factory()
        expected_ids = [users[i].id for i in expected_indexes]

        assert [user.id for user in query] == expected_ids
        assert [user.id for user in query.all()] == expected_ids
        assert query.count() == len(expected_ids)
        if expected_ids:
            assert query.first().id == expected_ids[0]
        else:
            assert query.first() is None

    @pytest.mark.parametrize('query_factory, expected_index', [
        (lambda: User.limit(2).order(id='asc'), 1),
        (lambda: User.offset(2).order(id='asc'), 4),
        (lambda: User.order(id='asc').limit(2).offset(1), 2),
        (lambda: User.order(id='desc').limit(2).offset(1), 2),
        (lambda: User.limit(0), None),
        (lambda: User.offset(5).limit(2), None),
        (lambda: User.limit(0).limit(None), 4),
        (lambda: User.offset(5).offset(None), 4),
    ])
    def test_last_respects_pagination(self, users, query_factory, expected_index):
        query = query_factory()
        expected_ids = [user.id for user in query]

        last = query.last()

        if expected_index is None:
            assert last is None
        else:
            assert last.id == users[expected_index].id
        assert [user.id for user in query] == expected_ids

    def test_pagination_is_lazy(self, users, session, mocker):
        execute = mocker.spy(session, 'execute')

        query = User.order(id='asc').limit(2).offset(1)

        execute.assert_not_called()
        sql = query.to_sql()
        assert 'LIMIT 2 OFFSET 1' in sql
        assert [user.id for user in query] == [users[1].id, users[2].id]
        execute.assert_called_once()


class TestModelValidations:

    @pytest.mark.parametrize('field, comparison, valid_value, invalid_value', [
        ('quantity', {'less_than': 10}, 5, 20),
        ('quantity', {'greater_than': 10}, 20, 5),
        (
            'expires_at',
            {'greater_than': datetime.now}, datetime.now() + timedelta(days=1), datetime.now() - timedelta(days=1)
        ),
    ])
    def test_validation(self, init_models, field, comparison, valid_value, invalid_value):
        @rules(
            validates(field, comparison=comparison),
        )
        class Product(Model):
            pass

        init_models(Base, [
            (ProductBase, Product),
        ])

        product = Product.new(**{field: invalid_value})
        assert not product.save()
        assert product.errors.count == 1

        product = Product.new(**{field: valid_value})
        assert product.save()
        assert product.errors.count == 0
