from pavilion import module_wrapper


class BarWrapper(module_wrapper.ModuleWrapper):

    def __init__(self):
        super().__init__('bar',
                         description="",
                         version='1.2.0')
