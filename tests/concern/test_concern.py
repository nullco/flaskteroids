from flaskteroids.concern import Concern
from flaskteroids.rules import bind_rules, rules

registered_rules = []


def rule(name):
    def _(_):
        registered_rules.append(name)
    return _


@rules(
    rule('a')
)
class ConcernA(Concern):

    def do_a(self):
        self.done.append('a')

    @classmethod
    def a(cls):
        return "A"


@rules(
    rule('b')
)
class ConcernB(Concern):

    def do_b(self):
        self.done.append('b')

    @classmethod
    def b(cls):
        return "B"


@rules(
    rule('my')
)
class MyClass(ConcernA, ConcernB):
    def __init__(self) -> None:
        self.done = []

    def do_my_thing(self):
        pass


bind_rules(MyClass)


def test_concern_class_methods():
    assert MyClass.a() == 'A'
    assert MyClass.b() == 'B'


def test_concern_instance_methods():
    c = MyClass()
    c.do_a()
    c.do_b()


def test_concern_rules():
    assert registered_rules == ['a', 'b', 'my']
