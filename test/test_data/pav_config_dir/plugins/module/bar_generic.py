from pavilion import module_wrapper


class BarGenericWrapper(module_wrapper.ModuleWrapper):

    def __init__(self):
        super().__init__('bar')
