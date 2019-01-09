from pavilion import module_wrapper


class FooWrapper(module_wrapper.ModuleWrapper):

    def __init__(self):
        super().__init__('foo')
