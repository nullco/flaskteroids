import pytest
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String
from flaskteroids import model
from flaskteroids.model import (
    Model,
    before_validation,
    after_validation,
    before_save,
    around_save,
    after_save,
    before_create,
    after_create,
    before_update,
    after_update,
    before_destroy,
    around_destroy,
    after_destroy,
    after_commit,
    after_rollback,
    after_initialize,
    after_find,
)
from flaskteroids.rules import rules


Base = declarative_base()


class UserBase(Base):
    __tablename__ = 'users'

    id = Column(Integer(), primary_key=True, autoincrement=True)
    username = Column(String())


class TestCallbacks:

    def test_before_save_can_modify_attributes(self, init_models):
        @rules(before_save('_normalize'))
        class User(Model):
            def _normalize(self):
                self.username = self.username.strip().lower()

        init_models(Base, [(UserBase, User)])

        user = User.create(username='  HELLO  ')
        assert user.username == 'hello'

    def test_around_save_wraps_the_save(self, init_models):
        calls = []

        @rules(
            before_save('_before'),
            around_save('_around'),
            after_save('_after'),
        )
        class User(Model):
            def _before(self):
                calls.append('before_save')

            def _around(self):
                calls.append('around_save:before')
                yield
                calls.append('around_save:after')

            def _after(self):
                calls.append('after_save')

        init_models(Base, [(UserBase, User)])

        assert User.create(username='x')
        assert calls == ['before_save', 'around_save:before', 'around_save:after', 'after_save']

    def test_create_vs_update_callbacks(self, init_models):
        calls = []

        @rules(before_create('_on_create'), before_update('_on_update'))
        class User(Model):
            def _on_create(self):
                calls.append('create')

            def _on_update(self):
                calls.append('update')

        init_models(Base, [(UserBase, User)])

        user = User.create(username='x')
        assert calls == ['create']

        calls.clear()
        user.username = 'y'
        user.save()
        assert calls == ['update']

    def test_after_create_and_after_update(self, init_models):
        calls = []

        @rules(after_create('_on_create'), after_update('_on_update'))
        class User(Model):
            def _on_create(self):
                calls.append('create')

            def _on_update(self):
                calls.append('update')

        init_models(Base, [(UserBase, User)])

        user = User.create(username='x')
        assert calls == ['create']

        calls.clear()
        user.update(username='y')
        assert calls == ['update']

    def test_validation_callbacks(self, init_models):
        calls = []

        @rules(before_validation('_before'), after_validation('_after'))
        class User(Model):
            def _before(self):
                calls.append('before_validation')

            def _after(self):
                calls.append('after_validation')

        init_models(Base, [(UserBase, User)])

        User.create(username='x')
        assert calls == ['before_validation', 'after_validation']

    def test_validation_callbacks_skipped_when_validate_is_false(self, init_models):
        calls = []

        @rules(before_validation('_before'), after_validation('_after'))
        class User(Model):
            def _before(self):
                calls.append('before_validation')

            def _after(self):
                calls.append('after_validation')

        init_models(Base, [(UserBase, User)])

        User.new(username='x').save(validate=False)
        assert calls == []

    def test_before_save_halt(self, init_models):
        @rules(before_save('_abort'))
        class User(Model):
            def _abort(self):
                return False

        init_models(Base, [(UserBase, User)])

        user = User.new(username='x')
        assert user.save() is False
        assert user.is_new_record()

    def test_around_save_halt(self, init_models):
        @rules(around_save('_abort'))
        class User(Model):
            def _abort(self):
                return
                yield  # pragma: no cover

        init_models(Base, [(UserBase, User)])

        user = User.new(username='x')
        assert user.save() is False
        assert user.is_new_record()

    def test_destroy_callbacks(self, init_models):
        calls = []

        @rules(
            before_destroy('_before'),
            around_destroy('_around'),
            after_destroy('_after'),
        )
        class User(Model):
            def _before(self):
                calls.append('before_destroy')

            def _around(self):
                calls.append('around_destroy:before')
                yield
                calls.append('around_destroy:after')

            def _after(self):
                calls.append('after_destroy')

        init_models(Base, [(UserBase, User)])

        user = User.create(username='x')
        assert user.destroy() is True
        assert calls == ['before_destroy', 'around_destroy:before', 'around_destroy:after', 'after_destroy']

    def test_before_destroy_halt(self, init_models):
        @rules(before_destroy('_abort'))
        class User(Model):
            def _abort(self):
                return False

        init_models(Base, [(UserBase, User)])

        user = User.create(username='x')
        assert user.destroy() is False
        assert User.find_by(username='x')

    def test_if_condition_by_method_name(self, init_models):
        calls = []

        @rules(before_save('_cb', if_='_should_run'))
        class User(Model):
            def _cb(self):
                calls.append('cb')

            def _should_run(self):
                return self.username == 'yes'

        init_models(Base, [(UserBase, User)])

        User.create(username='no')
        assert calls == []

        User.create(username='yes')
        assert calls == ['cb']

    def test_unless_condition_by_callable(self, init_models):
        calls = []

        @rules(before_save('_cb', unless_=lambda user: user.username == 'skip'))
        class User(Model):
            def _cb(self):
                calls.append('cb')

        init_models(Base, [(UserBase, User)])

        User.create(username='skip')
        assert calls == []

        User.create(username='go')
        assert calls == ['cb']

    def test_on_option(self, init_models):
        calls = []

        @rules(before_save('_cb', on='create'))
        class User(Model):
            def _cb(self):
                calls.append('cb')

        init_models(Base, [(UserBase, User)])

        user = User.create(username='x')
        assert calls == ['cb']

        calls.clear()
        user.update(username='y')
        assert calls == []

    def test_before_callbacks_run_in_order(self, init_models):
        calls = []

        @rules(
            before_save('_first'),
            before_save('_second', prepend=True),
        )
        class User(Model):
            def _first(self):
                calls.append('first')

            def _second(self):
                calls.append('second')

        init_models(Base, [(UserBase, User)])

        User.create(username='x')
        assert calls == ['second', 'first']

    def test_after_callbacks_run_in_reverse_order(self, init_models):
        calls = []

        @rules(
            after_save('_first'),
            after_save('_second'),
        )
        class User(Model):
            def _first(self):
                calls.append('first')

            def _second(self):
                calls.append('second')

        init_models(Base, [(UserBase, User)])

        User.create(username='x')
        assert calls == ['second', 'first']

    def test_after_commit(self, init_models):
        calls = []

        @rules(after_commit('_cb'))
        class User(Model):
            def _cb(self):
                calls.append('after_commit')

        init_models(Base, [(UserBase, User)])

        User.create(username='x')
        assert calls == []

        model.session.commit()
        assert calls == ['after_commit']

    def test_after_rollback(self, init_models):
        calls = []

        @rules(after_rollback('_cb'))
        class User(Model):
            def _cb(self):
                calls.append('after_rollback')

        init_models(Base, [(UserBase, User)])

        User.create(username='x')
        assert calls == []

        model.session.rollback()
        assert calls == ['after_rollback']

    def test_after_initialize(self, init_models):
        calls = []

        @rules(after_initialize('_cb'))
        class User(Model):
            def _cb(self):
                calls.append('initialize')

        init_models(Base, [(UserBase, User)])

        User.new(username='x')
        assert calls == ['initialize']

        user = User.create(username='x')
        calls.clear()
        User.find(user.id)
        assert calls == ['initialize']

    def test_after_find(self, init_models):
        calls = []

        @rules(after_find('_cb'))
        class User(Model):
            def _cb(self):
                calls.append('find')

        init_models(Base, [(UserBase, User)])

        user = User.create(username='x')
        assert calls == []

        User.find(user.id)
        assert calls == ['find']

    def test_on_is_not_supported_on_create_callbacks(self, init_models):
        from flaskteroids.exceptions import ProgrammerError

        @rules(before_create('_cb', on='update'))
        class User(Model):
            def _cb(self):
                pass

        with pytest.raises(ProgrammerError):
            init_models(Base, [(UserBase, User)])

    def test_on_is_not_supported_on_destroy_callbacks(self, init_models):
        from flaskteroids.exceptions import ProgrammerError

        @rules(before_destroy('_cb', on='destroy'))
        class User(Model):
            def _cb(self):
                pass

        with pytest.raises(ProgrammerError):
            init_models(Base, [(UserBase, User)])

    def test_on_allows_destroy_for_after_commit(self, init_models):
        calls = []

        @rules(after_commit('_cb', on='destroy'))
        class User(Model):
            def _cb(self):
                calls.append('after_commit_destroy')

        init_models(Base, [(UserBase, User)])

        user = User.create(username='x')
        model.session.commit()
        assert calls == []

        user.destroy()
        model.session.commit()
        assert calls == ['after_commit_destroy']

    def test_callbacks_are_inherited(self, init_models):
        calls = []

        @rules(before_save('_cb'))
        class BaseUser(Model):
            def _cb(self):
                calls.append('cb')

        @rules()
        class User(BaseUser):
            pass

        init_models(Base, [(UserBase, User)])

        User.create(username='x')
        assert calls == ['cb']
