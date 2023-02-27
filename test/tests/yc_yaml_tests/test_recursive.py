
import yc_yaml as yaml

class AnInstance:

    def __init__(self, foo, bar):
        self.foo = foo
        self.bar = bar

    def __repr__(self):
        try:
            return "%s(foo=%r, bar=%r)" % (self.__class__.__name__,
                    self.foo, self.bar)
        except RuntimeError:
            return "%s(foo=..., bar=...)" % self.__class__.__name__

class AnInstanceWithState(AnInstance):

    def __getstate__(self):
        return {'attributes': [self.foo, self.bar]}

    def __setstate__(self, state):
        self.foo, self.bar = state['attributes']

def test_recursive(recursive_filename, verbose=False):
    context = globals().copy()
    exec(open(recursive_filename, 'rb').read(), context)
    value1 = context['value']
    output1 = None
    value2 = None
    output2 = None
    try:
        output1 = yaml.danger_dump(value1)
        value2 = yaml.danger_load(output1)
        output2 = yaml.danger_dump(value2)
        assert output1 == output2, (output1, output2)
    finally:
        if verbose:
            print("VALUE1:", value1)  # ext-print: ignore
            print("VALUE2:", value2)  # ext-print: ignore
            print("OUTPUT1:")  # ext-print: ignore
            print(output1)  # ext-print: ignore
            print("OUTPUT2:")  # ext-print: ignore
            print(output2)  # ext-print: ignore

test_recursive.unittest = ['.recursive']

if __name__ == '__main__':
    import test_appliance
    test_appliance.run(globals())
