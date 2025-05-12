from flaskteroids.rules import rules, bind_rules
from flaskteroids.registry import get


def rule(name):
    def bind(cls):
        ns = get(cls)
        if 'test_rules' not in ns:
            ns['test_rules'] = []
        ns['test_rules'].append(name)
    return bind


@rules(
    rule('one'),
    rule('two')
)
class Parent:
    pass


@rules(
    rule('three')
)
class Child(Parent):
    pass


def test_rules():
    bind_rules(Child)
    ns = get(Child)
    assert ns['test_rules'] == ['one', 'two', 'three']
