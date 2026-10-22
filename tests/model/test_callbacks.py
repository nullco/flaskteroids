import pytest
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

from flaskteroids import model
from flaskteroids.model import (
    after_commit,
    after_create,
    after_destroy,
    after_find,
    after_initialize,
    after_rollback,
    after_save,
    after_update,
    after_validation,
    around_destroy,
    around_save,
    before_create,
    before_destroy,
    before_save,
    before_update,
    before_validation,
)
from tests.model.schema_support import model_base

Base = declarative_base()


class UserBase(Base):
    __tablename__ = "users"

    id = Column(Integer(), primary_key=True, autoincrement=True)
    username = Column(String())


def test_plain_mixin_diamonds_contribute_validations_and_callbacks(init_models):
    events = []

    class NormalizedName:
        model.validates("username", presence=True)
        before_validation("_normalize_name")

        def _normalize_name(self):
            events.append("normalize")
            if self.username:
                self.username = self.username.strip()

    class Left(NormalizedName):
        pass

    class Right(NormalizedName):
        pass

    class User(Left, Right, model_base(Base)):
        pass

    init_models(Base, [(UserBase, User)])
    user = User.new(username="  Ada  ")
    assert user.is_valid() is True
    assert user.username == "Ada"
    assert events == ["normalize"]
    user.username = "  "
    assert user.is_valid() is False
    assert user.errors


class TestCallbacks:
    def test_before_save_can_modify_attributes(self, init_models):
        class User(model_base(Base)):
            before_save("_normalize")

            def _normalize(self):
                self.username = self.username.strip().lower()

        init_models(Base, [(UserBase, User)])

        user = User.create(username="  HELLO  ")
        assert user.username == "hello"

    def test_around_save_wraps_the_save(self, init_models):
        calls = []

        class User(model_base(Base)):
            before_save("_before")
            around_save("_around")
            after_save("_after")

            def _before(self):
                calls.append("before_save")

            def _around(self):
                calls.append("around_save:before")
                yield
                calls.append("around_save:after")

            def _after(self):
                calls.append("after_save")

        init_models(Base, [(UserBase, User)])

        assert User.create(username="x")
        assert calls == [
            "before_save",
            "around_save:before",
            "around_save:after",
            "after_save",
        ]

    def test_before_callbacks_run_for_matching_persistence_operation(self, init_models):
        calls = []

        class User(model_base(Base)):
            before_create("_on_create")
            before_update("_on_update")

            def _on_create(self):
                calls.append("create")

            def _on_update(self):
                calls.append("update")

        init_models(Base, [(UserBase, User)])

        user = User.create(username="x")
        assert calls == ["create"]

        calls.clear()
        user.username = "y"
        user.save()
        assert calls == ["update"]

    def test_after_callbacks_run_for_matching_persistence_operation(self, init_models):
        calls = []

        class User(model_base(Base)):
            after_create("_on_create")
            after_update("_on_update")

            def _on_create(self):
                calls.append("create")

            def _on_update(self):
                calls.append("update")

        init_models(Base, [(UserBase, User)])

        user = User.create(username="x")
        assert calls == ["create"]

        calls.clear()
        user.update(username="y")
        assert calls == ["update"]

    def test_validation_callbacks_wrap_validation_in_order(self, init_models):
        calls = []

        class User(model_base(Base)):
            before_validation("_before")
            after_validation("_after")

            def _before(self):
                calls.append("before_validation")

            def _after(self):
                calls.append("after_validation")

        init_models(Base, [(UserBase, User)])

        User.create(username="x")
        assert calls == ["before_validation", "after_validation"]

    def test_validation_callbacks_skipped_when_validate_is_false(self, init_models):
        calls = []

        class User(model_base(Base)):
            before_validation("_before")
            after_validation("_after")

            def _before(self):
                calls.append("before_validation")

            def _after(self):
                calls.append("after_validation")

        init_models(Base, [(UserBase, User)])

        User.new(username="x").save(validate=False)
        assert calls == []

    def test_before_save_halts_persistence_when_callback_returns_false(
        self, init_models
    ):
        class User(model_base(Base)):
            before_save("_abort")

            def _abort(self):
                return False

        init_models(Base, [(UserBase, User)])

        user = User.new(username="x")
        assert user.save() is False
        assert user.is_new_record()

    def test_around_save_halts_persistence_when_callback_stops_before_yield(
        self, init_models
    ):
        class User(model_base(Base)):
            around_save("_abort")

            def _abort(self):
                return
                yield  # pragma: no cover

        init_models(Base, [(UserBase, User)])

        user = User.new(username="x")
        assert user.save() is False
        assert user.is_new_record()

    def test_destroy_callbacks_wrap_deletion_in_order(self, init_models):
        calls = []

        class User(model_base(Base)):
            before_destroy("_before")
            around_destroy("_around")
            after_destroy("_after")

            def _before(self):
                calls.append("before_destroy")

            def _around(self):
                calls.append("around_destroy:before")
                yield
                calls.append("around_destroy:after")

            def _after(self):
                calls.append("after_destroy")

        init_models(Base, [(UserBase, User)])

        user = User.create(username="x")
        assert user.destroy() is True
        assert calls == [
            "before_destroy",
            "around_destroy:before",
            "around_destroy:after",
            "after_destroy",
        ]

    def test_before_destroy_halts_deletion_when_callback_returns_false(
        self, init_models
    ):
        class User(model_base(Base)):
            before_destroy("_abort")

            def _abort(self):
                return False

        init_models(Base, [(UserBase, User)])

        user = User.create(username="x")
        assert user.destroy() is False
        assert User.find_by(username="x")

    def test_callbacks_evaluate_named_if_condition(self, init_models):
        calls = []

        class User(model_base(Base)):
            before_save("_cb", if_="_should_run")

            def _cb(self):
                calls.append("cb")

            def _should_run(self):
                return self.username == "yes"

        init_models(Base, [(UserBase, User)])

        User.create(username="no")
        assert calls == []

        User.create(username="yes")
        assert calls == ["cb"]

    def test_callbacks_evaluate_callable_unless_condition(self, init_models):
        calls = []

        class User(model_base(Base)):
            before_save("_cb", unless_=lambda user: user.username == "skip")

            def _cb(self):
                calls.append("cb")

        init_models(Base, [(UserBase, User)])

        User.create(username="skip")
        assert calls == []

        User.create(username="go")
        assert calls == ["cb"]

    def test_callbacks_apply_on_filter_to_save_operations(self, init_models):
        calls = []

        class User(model_base(Base)):
            before_save("_cb", on="create")

            def _cb(self):
                calls.append("cb")

        init_models(Base, [(UserBase, User)])

        user = User.create(username="x")
        assert calls == ["cb"]

        calls.clear()
        user.update(username="y")
        assert calls == []

    def test_before_callbacks_run_in_order(self, init_models):
        calls = []

        class User(model_base(Base)):
            before_save("_first")
            before_save("_second", prepend=True)

            def _first(self):
                calls.append("first")

            def _second(self):
                calls.append("second")

        init_models(Base, [(UserBase, User)])

        User.create(username="x")
        assert calls == ["second", "first"]

    def test_after_callbacks_run_in_reverse_order(self, init_models):
        calls = []

        class User(model_base(Base)):
            after_save("_first")
            after_save("_second")

            def _first(self):
                calls.append("first")

            def _second(self):
                calls.append("second")

        init_models(Base, [(UserBase, User)])

        User.create(username="x")
        assert calls == ["second", "first"]

    def test_after_commit_runs_once_for_committed_save(self, init_models):
        calls = []

        class User(model_base(Base)):
            after_commit("_cb")

            def _cb(self):
                calls.append("after_commit")

        init_models(Base, [(UserBase, User)])

        User.create(username="x")
        assert calls == ["after_commit"]

        model.session.commit()
        assert calls == ["after_commit"]

    def test_after_rollback_runs_for_rolled_back_save(self, init_models):
        calls = []

        class User(model_base(Base)):
            after_rollback("_cb")

            def _cb(self):
                calls.append("after_rollback")

        init_models(Base, [(UserBase, User)])

        model.session.begin()
        User.create(username="x")
        assert calls == []

        model.session.rollback()
        assert calls == ["after_rollback"]

    def test_after_initialize_runs_for_new_and_freshly_loaded_records(
        self, init_models
    ):
        calls = []

        class User(model_base(Base)):
            after_initialize("_cb")

            def _cb(self):
                calls.append("initialize")

        init_models(Base, [(UserBase, User)])

        User.new(username="x")
        assert calls == ["initialize"]

        user = User.create(username="x")
        calls.clear()
        assert User.find(user.id) is user
        assert calls == []
        model.session.expunge(user)
        User.find(user.id)
        assert calls == ["initialize"]

    def test_after_find_runs_for_freshly_loaded_records(self, init_models):
        calls = []

        class User(model_base(Base)):
            after_find("_cb")

            def _cb(self):
                calls.append("find")

        init_models(Base, [(UserBase, User)])

        user = User.create(username="x")
        assert calls == []

        assert User.find(user.id) is user
        assert calls == []
        model.session.expunge(user)
        User.find(user.id)
        assert calls == ["find"]

    @pytest.mark.parametrize(
        "callback, operation", [(before_create, "update"), (before_destroy, "destroy")]
    )
    def test_operation_specific_callbacks_reject_on_option(
        self, init_models, callback, operation
    ):
        from flaskteroids.exceptions import ProgrammerError

        class User(model_base(Base)):
            callback("_cb", on=operation)

            def _cb(self):
                pass

        with pytest.raises(ProgrammerError):
            init_models(Base, [(UserBase, User)])

    def test_on_allows_destroy_for_after_commit(self, init_models):
        calls = []

        class User(model_base(Base)):
            after_commit("_cb", on="destroy")

            def _cb(self):
                calls.append("after_commit_destroy")

        init_models(Base, [(UserBase, User)])

        user = User.create(username="x")
        model.session.commit()
        assert calls == []

        user.destroy()
        model.session.commit()
        assert calls == ["after_commit_destroy"]

    def test_callbacks_are_inherited(self, init_models):
        calls = []

        class BaseUser(model_base(Base)):
            before_save("_cb")
            __abstract__ = True

            def _cb(self):
                calls.append("cb")

        class User(BaseUser):
            pass

        init_models(Base, [(UserBase, User)])

        User.create(username="x")
        assert calls == ["cb"]

    def test_aborted_create_preserves_new_record_and_skips_after_save(
        self, init_models
    ):
        calls = []

        class User(model_base(Base)):
            before_create("_abort")
            after_save("_after")

            def _abort(self):
                return False

            def _after(self):
                calls.append("after_save")

        init_models(Base, [(UserBase, User)])
        user = User.create(username="x")
        assert user.is_new_record()
        assert User.count() == 0
        assert calls == []
