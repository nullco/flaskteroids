from flaskteroids.rules import bind_rules, rules


def rule(name):
    def bind(cls):
        if "test_rules" not in vars(cls):
            cls.test_rules = []
        cls.test_rules.append(name)

    return bind


@rules(rule("one"), rule("two"))
class Parent:
    pass


@rules(rule("three"))
class Child(Parent):
    pass


def test_rules():
    bind_rules(Child)
    assert Child.test_rules == ["one", "two", "three"]
